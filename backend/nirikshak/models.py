from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "guaranteed_returns",
    "stock_tip",
    "price_prediction",
    "urgency_fomo",
    "paid_promotion",
    "paid_group",
    "registration_claim",
    "misleading_claim",
    "credential_request",
    "suspicious_link",
    "upfront_payment",
    "impersonation",
]


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Source(BaseModel):
    kind: Literal["youtube", "upload", "message"]
    url: str | None = None
    video_id: str | None = None
    title: str = ""
    channel: str = ""
    description: str = ""
    duration: float = 0
    language: str | None = None
    transcript_source: Literal["captions", "whisper"] | None = None
    channel_id: str | None = None
    upload_date: str | None = None  # YYYYMMDD


class Claim(BaseModel):
    start: float
    end: float
    quote: str
    category: Category
    severity: int = Field(ge=1, le=3)
    confidence: float = Field(ge=0, le=1)
    why_en: str
    why_hi: str = ""
    origin: Literal["llm", "rules", "llm+rules"] = "llm"
    where: Literal["transcript", "description"] = "transcript"


class RegistryHit(BaseModel):
    reg_no: str
    name: str
    category: str
    validity: str = ""
    score: float = 100
    how: str = ""  # number | near_number | name | contact_person | domain


class IdentityCheck(BaseModel):
    """One name, website or number we looked up, and what it matched."""
    query: str
    kind: Literal["number", "name", "domain"]
    role: Literal["channel", "owner", "speaker", "guest", "company", "website", "number"]
    source: Literal["channel", "title", "description", "transcript"]
    hits: list[RegistryHit] = []


class RegistryCheck(BaseModel):
    claims_registration: bool
    numbers_found: list[str]
    number_results: dict[str, RegistryHit | None]
    name_matches: list[RegistryHit]
    disclaimer_found: bool
    disclaimer_quotes: list[str]
    verdict: Literal["verified", "matched", "registered_other", "guests_registered", "number_not_found",
                     "claimed_unverified", "possible_match", "not_registered", "unknown"]
    checks: list[IdentityCheck] = []
    entity: RegistryHit | None = None  # the registration the verdict is about, if any


class Concern(BaseModel):
    start: float
    where: Literal["transcript", "description"]
    category: Category
    severity: int
    quote: str
    why: str


class Summary(BaseModel):
    """Structured audit brief in one language. Only `headline` and `overview` are
    LLM-written; the rest is built from verified findings and the registry check."""
    headline: str
    overview: str
    concerns: list[Concern]
    registration: str
    advice: list[str]


class Report(BaseModel):
    id: str
    created_at: str
    source: Source
    segments: list[Segment]
    claims: list[Claim]
    registry: RegistryCheck
    risk_score: int
    risk_level: Literal["low", "medium", "high"]
    summary_en: str
    summary_hi: str
    summary: dict[str, Summary] | None = None  # {"en": …, "hi": …}
    private: bool = False  # message checks the user chose not to keep in history
    model: str
    timings: dict[str, float]


class ProfileVideo(BaseModel):
    report_id: str
    video_id: str
    title: str
    position: int  # 0 = newest upload in the profile
    upload_date: str | None = None
    risk_score: int
    risk_level: Literal["low", "medium", "high"]
    categories: list[Category]
    verdict: str
    disclaimer: bool


class WorstMoment(BaseModel):
    report_id: str
    video_title: str
    start: float
    category: Category
    severity: int
    quote: str
    why_en: str
    why_hi: str


class Profile(BaseModel):
    id: str  # channel id
    channel: str
    channel_url: str
    created_at: str
    videos: list[ProfileVideo]
    category_videos: dict[str, int]  # category -> number of videos with a strong finding of it
    avg_risk: float
    median_risk: float
    max_risk: int
    level: Literal["low", "medium", "high"]
    disclaimer_rate: float
    registry: "RegistryCheck"
    worst: list[WorstMoment]
    headline: dict[str, str]  # {"en": …, "hi": …}
