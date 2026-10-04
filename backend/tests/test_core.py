"""Fast tests that need no network, GPU or LLM."""
from nirikshak import analyse, rules, sebi
from nirikshak.models import Claim, RegistryCheck, Segment
from nirikshak.pipeline import score


def cats(text: str) -> set[str]:
    return {h.category for h in rules.scan_text(text)}


def test_guarantee_english_and_devanagari():
    assert "guaranteed_returns" in cats("Get guaranteed returns of 5% daily")
    assert "guaranteed_returns" in cats("इसमें पक्का मुनाफा मिलेगा")


def test_stock_tip_with_levels():
    assert "stock_tip" in cats("Buy Tata Power above 412, target 450, stop loss 398")
    assert "stock_tip" in cats("टारगेट 30 रुपए रखो और स्टॉप लॉस 21")


def test_registration_claim_ignores_negation():
    assert "registration_claim" in cats("I am a SEBI registered research analyst")
    assert "registration_claim" not in cats("We are not SEBI registered. For education only.")
    assert "registration_claim" not in cats("I am not a SEBI registered adviser")


def test_reg_number_and_disclaimer_extraction():
    assert rules.find_reg_numbers("Reg no: INH 000011431, also INA-000012345") == ["INH000011431", "INA000012345"]
    assert rules.find_disclaimers("This is for educational purposes only.")
    assert not rules.find_disclaimers("Buy now, guaranteed.")


def test_sebi_card_parsing_handles_both_quote_styles():
    html = (
        "<div class='card-view'><div class='title'><span>Name</span></div><div class='value varun-text'><span>Acme Research</span></div></div>"
        '<div class="card-view"><div class="title"><span>Registration No.</span></div><div class="value"><span>INH000000001</span></div></div>'
        "<div class='card-view'><div class='title'><span> Validity </span></div><div class='value'><span>Jan 1, 2024 - Perpetual</span></div></div>"
    )
    recs = sebi._parse(html, "Research Analyst")
    assert recs == [{"name": "Acme Research", "category": "Research Analyst", "reg_no": "INH000000001", "validity": "Jan 1, 2024 - Perpetual"}]


def test_name_normalisation_drops_corporate_suffixes():
    assert sebi._norm("Acme Research Advisory Private Limited") == "acme"


def _claim(cat, sev=3, conf=0.9, start=0.0):
    return Claim(start=start, end=start + 5, quote="x", category=cat, severity=sev, confidence=conf, why_en="w")


def _reg(verdict="not_registered", disclaimer=False):
    return RegistryCheck(claims_registration=False, numbers_found=[], number_results={}, name_matches=[],
                         disclaimer_found=disclaimer, disclaimer_quotes=[], verdict=verdict)


def test_score_levels():
    assert score([], _reg())[1] == "low"
    many = [_claim("guaranteed_returns"), _claim("stock_tip"), _claim("urgency_fomo", 2), _claim("paid_group", 2)]
    s, level = score(many, _reg())
    assert level == "high" and s >= 55


def test_score_caps_repeated_category():
    one_cat = [_claim("urgency_fomo", 2, start=i * 10) for i in range(20)]
    assert score(one_cat, _reg(disclaimer=True))[0] <= 3 * 2 * 0.9 * 9 + 1


def test_grounding_drops_hallucinated_quotes(monkeypatch):
    segs = [Segment(start=0, end=5, text="Buy this stock now, target 500")]
    fake = {"claims": [
        {"line": 0, "quote": "Buy this stock now", "category": "stock_tip", "severity": 3, "confidence": 0.9, "why_en": "a"},
        {"line": 0, "quote": "you will become a crorepati in a week", "category": "guaranteed_returns",
         "severity": 3, "confidence": 0.9, "why_en": "b"},
    ]}
    monkeypatch.setattr(analyse, "_chat", lambda *a, **k: fake)
    out = analyse.analyse_window(segs, [0], [], "test")
    assert [c.category for c in out] == ["stock_tip"]


def test_merge_adds_uncovered_rule_hits_at_low_confidence():
    hits = rules.scan_segments([Segment(start=10, end=15, text="guaranteed returns every month")])
    merged = analyse.merge([], hits)
    assert merged and merged[0].origin == "rules" and merged[0].confidence < 0.5


def test_fixed_income_asset_class_is_not_a_guarantee():
    assert "guaranteed_returns" not in cats("Fixed income instruments like bonds and FDs")
    assert "guaranteed_returns" in cats("You get fixed returns of 3% a month")


def test_rule_agreement_does_not_lift_unlikely_claim():
    hits = rules.scan_segments([Segment(start=0, end=5, text="guaranteed returns every month")])
    weak = _claim("guaranteed_returns", conf=0.4)
    assert analyse.merge([weak], hits)[0].confidence == 0.4


def test_mistyped_reg_number_is_ambiguous_without_name():
    # INH00008984 (creator dropped a digit of INH100008984) is one edit from several
    # real registrations, so a near match alone must not pick one.
    near = {h.reg_no for h in sebi.near_numbers("INH00008984")}
    assert "INH100008984" in near and len(near) > 1
    assert sebi.lookup_number("INH00008984", live=False) is None


def test_typo_number_verified_when_it_is_the_channels_own(monkeypatch):
    from functools import partial

    from nirikshak.models import Source
    from nirikshak.pipeline import check_registry

    from nirikshak import identity

    monkeypatch.setattr(sebi, "lookup_number", partial(sebi.lookup_number, live=False))  # no network in tests
    monkeypatch.setattr(identity, "extract_people", lambda *a: [])  # no LLM in tests
    src = Source(kind="youtube", channel="Rakesh Bansal", description="SEBI Registration Number:INH00008984")
    reg = check_registry(src, [], [])
    assert reg.verdict == "verified" and reg.number_results["INH00008984"].reg_no == "INH100008984"
    fake = check_registry(Source(kind="youtube", channel="Random Tips Guru", description="SEBI reg INH00008984"), [], [])
    assert fake.verdict != "verified"


def test_channel_name_matches_registered_entity_with_suffix():
    assert any(h.reg_no == "INH100008984" for h in sebi.match_names("Rakesh Bansal"))


def test_registration_claim_needs_registration_words():
    assert not analyse._plausible({"category": "registration_claim", "quote": "the most trusted place in stock market"})
    assert analyse._plausible({"category": "registration_claim", "quote": "We are SEBI Registered"})


def test_claim_whose_explanation_is_a_warning_is_dropped():
    assert not analyse._plausible({"category": "misleading_claim", "quote": "x",
                                   "why_en": "The speaker warns against fraudulent schemes that promise high returns."})
    assert analyse._plausible({"category": "guaranteed_returns", "quote": "x",
                               "why_en": "Promising fixed returns is a red flag."})


def test_summary_parts_built_from_findings_not_llm():
    from nirikshak import summary
    claims = [_claim("guaranteed_returns", start=30), _claim("paid_group", 2, start=90), _claim("urgency_fomo", 2, 0.3)]
    top = summary.top_concerns(claims)
    assert [c.category for c in top] == ["guaranteed_returns", "paid_group"]  # weak signal excluded
    adv = summary.advice(claims, _reg(), "en")
    assert any("guarantee" in a for a in adv) and len(adv) <= 4
    clean = summary.registration_text(_reg(), "Edu Channel", "en", advises=False)
    assert "does not" in clean


def test_speech_text_normalisation():
    from nirikshak import tts
    en = tts.normalise("Buy/sell call: 100X returns, join https://t.me/x (INH000011431)", "en")
    assert "or" in en and "100 times" in en and "http" not in en and "INH" not in en
    hi = tts.normalise("SEBI और Telegram पर खरीद/बिक्री, 100x", "hi")
    # Latin words make the Hindi phonemizer switch language mid-sentence, so they are converted.
    assert "सेबी" in hi and "टेलीग्राम" in hi and "या" in hi and "गुना" in hi
    assert not any("a" <= ch.lower() <= "z" for ch in hi)



def test_affiliate_domain_is_not_treated_as_the_creator():
    from nirikshak import identity
    desc = "Open a demat account: https://zerodha.com/open-account?c=XYZ  My site: https://ankurwarikoo.com"
    assert identity.own_domains(desc, ["warikoo"]) == ["ankurwarikoo.com"]
    assert identity.own_domains("https://zerodha.com/varsity", ["Zero1 by Zerodha"]) == ["zerodha.com"]


def test_name_matching_is_strict_for_people():
    assert sebi._norm("CA Rachana Phadke Ranade") == "rachana phadke ranade"
    assert sebi.match_name("Random Tips Guru") == []
    assert any(h.reg_no == "INH100008984" for h in sebi.match_name("Rakesh Bansal"))


def test_verdict_prefers_adviser_and_flags_broker_only():
    from nirikshak.identity import verdict
    from nirikshak.models import IdentityCheck, RegistryHit
    adv = RegistryHit(reg_no="INH1", name="A", category="Research Analyst", score=100, how="name")
    brk = RegistryHit(reg_no="INZ1", name="B Broking", category="Stock Broker", score=100, how="name")
    ch = lambda hits, role="channel": IdentityCheck(query="x", kind="name", role=role, source="channel", hits=hits)
    assert verdict([ch([adv])], False)[0] == "matched"
    assert verdict([ch([brk])], False)[0] == "registered_other"
    assert verdict([ch([]), ch([adv], "guest")], False)[0] == "guests_registered"
    num = IdentityCheck(query="INH9", kind="number", role="number", source="description", hits=[])
    assert verdict([num, ch([])], True)[0] == "number_not_found"
