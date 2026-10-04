"""Local mirror of SEBI's public registers, and identity matching against it.

`sync()` mirrors several of SEBI's "Recognised intermediaries" lists into SQLite
(and a CSV snapshot that ships with the repo):

- Research Analysts and Investment Advisers: the only intermediaries allowed to
  give buy/sell recommendations or investment advice to the public.
- Stock Brokers, Portfolio Managers and Mutual Funds: registered, but not
  permitted to give such tips. Knowing these lets the audit say "registered, but
  as a broker" instead of a misleading "not found" (e.g. Zerodha).

For privacy only the domain of each contact e-mail is stored, never the address.
"""
from __future__ import annotations

import csv
import html
import re
import sqlite3
import time
from contextlib import contextmanager
from typing import Callable, Iterator

import httpx
from rapidfuzz import fuzz, process
from rapidfuzz.distance import Levenshtein

from .config import SEBI_CSV, SEBI_DB
from .models import RegistryHit

BASE = "https://www.sebi.gov.in"
PAGE = BASE + "/sebiweb/other/OtherAction.do?doRecognisedFpi=yes&intmId={id}"
AJAX = BASE + "/sebiweb/ajax/other/getintmfpiinfo.jsp"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0 Safari/537.36"

CATEGORIES = {
    13: "Investment Adviser",
    14: "Research Analyst",
    33: "Portfolio Manager",
    30: "Stock Broker",
    23: "Mutual Fund",
}
# Only these may give investment advice / buy-sell recommendations to the public.
ADVICE_CATEGORIES = {"Investment Adviser", "Research Analyst"}
# Display/selection order when one name has several registrations.
CATEGORY_ORDER = ["Research Analyst", "Investment Adviser", "Portfolio Manager", "Stock Broker", "Mutual Fund"]
# How strong each kind of match is as evidence that this entity is the creator.
HOW_ORDER = {"number": 0, "domain": 1, "near_number": 2, "name": 3, "contact_person": 4, "": 5}


def rank(h: RegistryHit) -> tuple:
    return (HOW_ORDER.get(h.how, 5), -h.score, CATEGORY_ORDER.index(h.category) if h.category in CATEGORY_ORDER else 9)


# Registration-number prefix → intmId, for live lookups of numbers we don't have locally.
PREFIX_LIST = {"INA": 13, "INH": 14, "INP": 33, "INZ": 30}

FIELDS = ["reg_no", "name", "trade_name", "category", "validity", "contact_person", "email_domain", "website_domain"]

CARD = re.compile(
    r"""<div class=["']card-view["'][^>]*><div class=["']title["']><span>\s*([^<]*?)\s*</span></div>"""
    r"""<div class=["']value[^"']*["']><span>(.*?)</span></div></div>""",
    re.S,
)
LAST_PAGE = re.compile(r"""searchFormFpi\('n',\s*'(\d+)'\);["']\s*title=["']Last""")

# Words that say what kind of company something is, not who it is.
SUFFIXES = re.compile(
    r"\b(private|pvt|limited|ltd|llp|research|advisory|advisors?|advisers?|investment|"
    r"securities|services|financial|capital|consultancy|consultants?|and|&|the|india|wealth|"
    r"ventures?|solutions?|associates?|enterprises?|group|fintech|analytics|markets?|investments?|"
    r"opc|proprietor|proprietorship|broking|brokers?|stock|stocks|shares?|commodities|"
    r"mutual|fund|funds|asset|management|amc|portfolio|managers?|co|company|corporation|corp|inc)\b\.?",
    re.I,
)
HONORIFICS = re.compile(r"\b(ca|cs|cfa|cfp|cma|dr|mr|mrs|ms|miss|sir|shri|smt|prof|er|adv)\b\.?", re.I)
FREE_MAIL = {"gmail.com", "yahoo.com", "yahoo.co.in", "hotmail.com", "outlook.com", "rediffmail.com",
             "icloud.com", "live.com", "protonmail.com", "ymail.com", "aol.com", "zoho.com"}


def _form(intm_id: int, page: int, reg_no: str = "", name: str = "") -> dict:
    return {
        "nextValue": "1", "next": "s" if (reg_no or name) else "n", "intmId": str(intm_id),
        "contPer": "", "name": name, "regNo": reg_no, "email": "", "location": "",
        "exchange": "", "affiliate": "", "alp": "", "language": "2", "model": "",
        "esgCategory": "", "doDirect": str(page if not (reg_no or name) else -1), "intmIds": "",
    }


@contextmanager
def _client(intm_id: int) -> Iterator[httpx.Client]:
    with httpx.Client(headers={"User-Agent": UA}, timeout=30, follow_redirects=True) as c:
        c.get(PAGE.format(id=intm_id))  # establishes the session cookie SEBI's WAF expects
        c.headers.update({
            "Referer": PAGE.format(id=intm_id),
            "Origin": BASE,
            "X-Requested-With": "XMLHttpRequest",
        })
        yield c


def domain_of(value: str) -> str:
    """'a@b.zerodha.com' / 'https://www.zerodha.com/x' → 'zerodha.com' (registrable part, roughly)."""
    v = value.strip().lower()
    v = v.split("@")[-1]
    v = re.sub(r"^[a-z]+://", "", v).split("/")[0].split("?")[0]
    v = v.removeprefix("www.")
    parts = v.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "org", "net", "gov", "ac"} and len(parts[-1]) == 2:
        return ".".join(parts[-3:])  # zerodha.co.in
    return ".".join(parts[-2:]) if len(parts) >= 2 else ""


def _parse(page_html: str, category: str) -> list[dict]:
    records, cur = [], None
    for title, value in CARD.findall(page_html):
        value = html.unescape(re.sub(r"<[^>]+>", " ", value)).strip()
        title = title.strip().rstrip(".").lower()
        if title == "name":
            cur = {"name": value, "category": category}
            records.append(cur)
        elif cur is not None:
            if title.startswith("registration no"):
                cur["reg_no"] = value.replace(" ", "").upper()
            elif title == "validity":
                cur["validity"] = value
            elif title == "trade name":
                cur["trade_name"] = value
            elif title == "contact person":
                cur["contact_person"] = value
            elif title == "e-mail":
                d = domain_of(value)
                if d and d not in FREE_MAIL:
                    cur["email_domain"] = d
            elif title == "website":
                cur["website_domain"] = domain_of(value)
    return [r for r in records if r.get("reg_no")]


def sync(on_progress: Callable[[str], None] = print, delay: float = 0.6) -> int:
    rows: dict[str, dict] = {}
    for intm_id, category in CATEGORIES.items():
        with _client(intm_id) as c:
            first = c.post(AJAX, data=_form(intm_id, 0)).text
            last = int(m.group(1)) if (m := LAST_PAGE.search(first)) else 0
            for r in _parse(first, category):
                rows.setdefault(r["reg_no"], r)
            for page in range(1, last + 1):
                time.sleep(delay)
                for attempt in range(3):
                    try:
                        text = c.post(AJAX, data=_form(intm_id, page)).text
                        break
                    except httpx.HTTPError:
                        time.sleep(3 * (attempt + 1))
                else:
                    continue
                for r in _parse(text, category):
                    rows.setdefault(r["reg_no"], r)
                on_progress(f"{category}: page {page + 1}/{last + 1}, {len(rows)} records")
    if not rows:
        raise RuntimeError("SEBI returned no records (site layout or WAF may have changed).")
    with open(SEBI_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: r["reg_no"]):
            w.writerow({k: r.get(k, "") for k in FIELDS})
    build_db()
    return len(rows)


def build_db() -> None:
    SEBI_DB.unlink(missing_ok=True)
    con = sqlite3.connect(SEBI_DB)
    con.execute("CREATE TABLE reg (reg_no TEXT PRIMARY KEY, name TEXT, trade_name TEXT, category TEXT, "
                "validity TEXT, contact_person TEXT, email_domain TEXT, website_domain TEXT, "
                "norm TEXT, norm_trade TEXT, norm_person TEXT)")
    with open(SEBI_CSV, encoding="utf-8") as f:
        rows = []
        for r in csv.DictReader(f):
            r = {k: r.get(k) or "" for k in FIELDS}
            rows.append((*[r[k] for k in FIELDS], _norm(r["name"]), _norm(r["trade_name"]), _norm(r["contact_person"])))
        con.executemany(f"INSERT OR REPLACE INTO reg VALUES ({','.join('?' * 11)})", rows)
    con.execute("CREATE INDEX idx_email ON reg(email_domain)")
    con.execute("CREATE INDEX idx_web ON reg(website_domain)")
    con.commit()
    con.close()


def _norm(s: str) -> str:
    s = HONORIFICS.sub(" ", s.lower())
    s = SUFFIXES.sub(" ", s)
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def _db() -> sqlite3.Connection | None:
    if not SEBI_DB.exists():
        if not SEBI_CSV.exists():
            return None
        build_db()
    con = sqlite3.connect(SEBI_DB)
    cols = {r[1] for r in con.execute("PRAGMA table_info(reg)")}
    if "norm_trade" not in cols:  # database from an older version
        con.close()
        build_db()
        con = sqlite3.connect(SEBI_DB)
    return con


def registry_size() -> int:
    con = _db()
    if not con:
        return 0
    with con:
        return con.execute("SELECT COUNT(*) FROM reg").fetchone()[0]


def registry_counts() -> dict[str, int]:
    con = _db()
    if not con:
        return {}
    with con:
        return dict(con.execute("SELECT category, COUNT(*) FROM reg GROUP BY category").fetchall())


def _hit(row, score: float = 100, how: str = "number") -> RegistryHit:
    return RegistryHit(reg_no=row[0], name=row[1], category=row[2], validity=row[3], score=round(score, 1), how=how)


def lookup_number(reg_no: str, live: bool = True) -> RegistryHit | None:
    reg_no = reg_no.replace(" ", "").replace("-", "").upper()
    con = _db()
    if con:
        with con:
            row = con.execute("SELECT reg_no, name, category, validity FROM reg WHERE reg_no=?", (reg_no,)).fetchone()
        if row:
            return _hit(row)
    intm_id = PREFIX_LIST.get(reg_no[:3])
    if not live or intm_id is None:
        return None
    try:
        with _client(intm_id) as c:
            recs = _parse(c.post(AJAX, data=_form(intm_id, 0, reg_no=reg_no)).text, CATEGORIES[intm_id])
    except httpx.HTTPError:
        return None
    for r in recs:
        if r["reg_no"] == reg_no:
            return RegistryHit(reg_no=r["reg_no"], name=r["name"], category=r["category"],
                               validity=r.get("validity", ""), how="number")
    return None


def near_numbers(reg_no: str, max_dist: int = 2) -> list[RegistryHit]:
    """Registered numbers within `max_dist` edits of a (possibly mistyped) number.

    Mistyped numbers are common in descriptions, but one typo can sit next to several
    real registrations, so callers must disambiguate (e.g. by channel name) and must
    never treat a near match on its own as verification."""
    con = _db()
    if not con:
        return []
    reg_no = reg_no.replace(" ", "").replace("-", "").upper()
    with con:
        rows = con.execute("SELECT reg_no, name, category, validity FROM reg WHERE reg_no LIKE ?",
                           (reg_no[:3] + "%",)).fetchall()
    scored = [(Levenshtein.distance(reg_no, r[0]), r) for r in rows]
    best = min((d for d, _ in scored), default=None)
    if best is None or best == 0 or best > max_dist:
        return []
    return [_hit(r, 100 - 15 * d, "near_number") for d, r in scored if d == best]


def _tokens(s: str) -> set[str]:
    return {t for t in s.split() if len(t) >= 2}


def match_name(query: str, limit: int = 3) -> list[RegistryHit]:
    """Registered entities whose name, trade name or contact person matches `query`.

    Names collide, so this is strict:
    - one-word queries ("Zerodha") must equal the entity's distinctive name exactly;
    - multi-word person/company names must match all their words (in any order),
      or be a near-identical spelling (token_sort_ratio ≥ 92).
    """
    q = _norm(query)
    qt = _tokens(q)
    if not qt or len(q) < 4:
        return []
    con = _db()
    if not con:
        return []
    with con:
        rows = con.execute("SELECT reg_no, name, category, validity, norm, norm_trade, norm_person FROM reg").fetchall()
    hits: dict[str, RegistryHit] = {}

    def add(row, score, how):
        if row[0] not in hits or hits[row[0]].score < score:
            hits[row[0]] = _hit(row, score, how)

    for row in rows:
        for field, how in ((row[4], "name"), (row[5], "name"), (row[6], "contact_person")):
            if not field:
                continue
            if field == q:
                add(row, 100, how)
            elif len(qt) >= 2 and qt <= _tokens(field) and len(_tokens(field)) <= len(qt) + 1:
                add(row, 94, how)  # "rachana ranade" ⊂ "rachana phadke ranade"
    if len(qt) >= 2:
        norms = [r[4] for r in rows]
        for _, score, idx in process.extract(q, norms, scorer=fuzz.token_sort_ratio, limit=limit, score_cutoff=92):
            add(rows[idx], score, "name")
    return sorted(hits.values(), key=rank)[:limit]


def match_domain(domain: str) -> list[RegistryHit]:
    """Entities whose contact e-mail or website is on `domain` (e.g. zerodha.com)."""
    d = domain_of(domain)
    if not d or d in FREE_MAIL:
        return []
    con = _db()
    if not con:
        return []
    with con:
        rows = con.execute("SELECT reg_no, name, category, validity FROM reg WHERE email_domain=? OR website_domain=?",
                           (d, d)).fetchall()
    # Large groups register many entities on one domain; prefer adviser registrations.
    return sorted((_hit(r, 90, "domain") for r in rows), key=rank)[:5]


def match_names(*candidates: str, threshold: float = 0, limit: int = 3) -> list[RegistryHit]:
    """Backwards-compatible wrapper: best matches across several candidate names."""
    hits: dict[str, RegistryHit] = {}
    for c in candidates:
        for h in match_name(c, limit):
            if h.reg_no not in hits or hits[h.reg_no].score < h.score:
                hits[h.reg_no] = h
    return sorted(hits.values(), key=lambda h: -h.score)[:limit]
