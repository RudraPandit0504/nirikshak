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
]


class Segment(BaseModel):
    start: float
    end: float
    text: str


class Source(BaseModel):
    kind: Literal["youtube", "upload"]
    url: str | None = None
    video_id: str | None = None
    title: str = ""
    channel: str = ""
    description: str = ""
    duration: float = 0
    language: str | None = None
    transcript_source: Literal["captions", "whisper"] | None = None


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


class RegistryCheck(BaseModel):
    claims_registration: bool
    numbers_found: list[str]
    number_results: dict[str, RegistryHit | None]
    name_matches: list[RegistryHit]
    disclaimer_found: bool
    disclaimer_quotes: list[str]
    verdict: Literal["verified", "number_not_found", "claimed_unverified", "possible_match", "not_registered", "unknown"]


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
    model: str
    timings: dict[str, float]
