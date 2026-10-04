"""SEBI registered Research Analyst / Investment Adviser registry.

`sync()` mirrors SEBI's public "Recognised intermediaries" lists into SQLite
(and a CSV snapshot that ships with the repo). Lookups hit the local copy
first and fall back to a single live query by registration number.
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
CATEGORIES = {13: "Investment Adviser", 14: "Research Analyst"}

CARD = re.compile(
    r"""<div class=["']card-view["'][^>]*><div class=["']title["']><span>\s*([^<]*?)\s*</span></div>"""
    r"""<div class=["']value[^"']*["']><span>(.*?)</span></div></div>""",
    re.S,
)
LAST_PAGE = re.compile(r"""searchFormFpi\('n',\s*'(\d+)'\);["']\s*title=["']Last""")

SUFFIXES = re.compile(
    r"\b(private|pvt|limited|ltd|llp|research|advisory|advisors?|advisers?|investment|"
    r"securities|services|financial|capital|consultancy|consultants?|and|&|the|india|wealth|"
    r"ventures?|solutions?|associates?|enterprises?|group|fintech|analytics|markets?|investments?|"
    r"opc|proprietor|proprietorship)\b\.?",
    re.I,
)


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
    return [r for r in records if r.get("reg_no")]


def sync(on_progress: Callable[[str], None] = print, delay: float = 0.6) -> int:
    rows: dict[str, dict] = {}
    for intm_id, category in CATEGORIES.items():
        with _client(intm_id) as c:
            first = c.post(AJAX, data=_form(intm_id, 0)).text
            last = int(m.group(1)) if (m := LAST_PAGE.search(first)) else 0
            for r in _parse(first, category):
                rows[r["reg_no"]] = r
            for page in range(1, last + 1):
                time.sleep(delay)
                for r in _parse(c.post(AJAX, data=_form(intm_id, page)).text, category):
                    rows[r["reg_no"]] = r
                on_progress(f"{category}: page {page + 1}/{last + 1}, {len(rows)} records")
    if not rows:
        raise RuntimeError("SEBI returned no records (site layout or WAF may have changed).")
    with open(SEBI_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["reg_no", "name", "trade_name", "category", "validity"])
        w.writeheader()
        for r in sorted(rows.values(), key=lambda r: r["reg_no"]):
            w.writerow({k: r.get(k, "") for k in w.fieldnames})
    build_db()
    return len(rows)


def build_db() -> None:
    SEBI_DB.unlink(missing_ok=True)
    con = sqlite3.connect(SEBI_DB)
    con.execute("CREATE TABLE reg (reg_no TEXT PRIMARY KEY, name TEXT, trade_name TEXT, category TEXT, validity TEXT, norm TEXT)")
    with open(SEBI_CSV, encoding="utf-8") as f:
        con.executemany(
            "INSERT OR REPLACE INTO reg VALUES (?,?,?,?,?,?)",
            [(r["reg_no"], r["name"], r["trade_name"], r["category"], r["validity"],
              _norm(f'{r["name"]} {r["trade_name"]}')) for r in csv.DictReader(f)],
        )
    con.commit()
    con.close()


def _norm(s: str) -> str:
    s = SUFFIXES.sub(" ", s.lower())
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", s).split())


def _db() -> sqlite3.Connection | None:
    if not SEBI_DB.exists():
        if not SEBI_CSV.exists():
            return None
        build_db()
    return sqlite3.connect(SEBI_DB)


def registry_size() -> int:
    con = _db()
    if not con:
        return 0
    with con:
        return con.execute("SELECT COUNT(*) FROM reg").fetchone()[0]


def lookup_number(reg_no: str, live: bool = True) -> RegistryHit | None:
    reg_no = reg_no.replace(" ", "").replace("-", "").upper()
    con = _db()
    if con:
        with con:
            row = con.execute("SELECT reg_no, name, category, validity FROM reg WHERE reg_no=?", (reg_no,)).fetchone()
        if row:
            return RegistryHit(reg_no=row[0], name=row[1], category=row[2], validity=row[3])
    if not live:
        return None
    intm_id = 13 if reg_no.startswith("INA") else 14
    try:
        with _client(intm_id) as c:
            recs = _parse(c.post(AJAX, data=_form(intm_id, 0, reg_no=reg_no)).text, CATEGORIES[intm_id])
    except httpx.HTTPError:
        return None
    for r in recs:
        if r["reg_no"] == reg_no:
            return RegistryHit(reg_no=r["reg_no"], name=r["name"], category=r["category"], validity=r.get("validity", ""))
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
    return [RegistryHit(reg_no=r[0], name=r[1], category=r[2], validity=r[3], score=100 - 15 * d)
            for d, r in scored if d == best]


def match_names(*candidates: str, threshold: float = 88, limit: int = 3) -> list[RegistryHit]:
    """Fuzzy-match a channel / creator name against registered entities.

    This is deliberately conservative: names collide, so results are shown to
    the user as 'possible match – verify', never as proof.
    """
    con = _db()
    if not con:
        return []
    with con:
        rows = con.execute("SELECT reg_no, name, category, validity, norm FROM reg").fetchall()
    norms = [r[4] for r in rows]
    hits: dict[str, RegistryHit] = {}
    for cand in candidates:
        q = _norm(cand)
        if len(q) < 4:
            continue
        for _, score, idx in process.extract(q, norms, scorer=fuzz.token_sort_ratio, limit=limit):
            if score >= threshold:
                r = rows[idx]
                if r[0] not in hits or hits[r[0]].score < score:
                    hits[r[0]] = RegistryHit(reg_no=r[0], name=r[1], category=r[2], validity=r[3], score=round(score, 1))
    return sorted(hits.values(), key=lambda h: -h.score)[:limit]
