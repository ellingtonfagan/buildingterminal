"""Shared pydantic models — the structured shapes LLMs must produce, and the
API response shapes. Every dollar figure on these models is produced by
deterministic code, never by an LLM.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .classify.taxonomy import JobType


# --- Stage 2: classifier output -------------------------------------------
class Classification(BaseModel):
    """Strict classifier output. The model returns a taxonomy label and a short
    rationale — no numbers, no confidence score."""

    job_type: JobType
    rationale: str = Field(default="", description="Short justification; audit only, never used as a number.")


# --- Stage 4: LLM-structured job spec -------------------------------------
class JobSpec(BaseModel):
    """The LLM structures a plain-language job description into this. It must not
    contain any dollar figure — the model never sees or produces costs here."""

    job_type: JobType
    scope_indicators: list[str] = Field(default_factory=list)
    missing_info_questions: list[str] = Field(default_factory=list)


# --- Stage 3/4: deterministic estimate ------------------------------------
class BuildingCharacteristics(BaseModel):
    bbl: str | None = None
    zipcode: str | None = None
    borough: str | None = None
    year_built: int | None = None
    num_floors: float | None = None
    units_res: int | None = None
    units_total: int | None = None
    res_area: int | None = None
    bldg_area: int | None = None
    bldg_class: str | None = None


class CostRange(BaseModel):
    p25: float | None
    p50: float | None
    p75: float | None
    per_unit_p50: float | None = None
    per_sqft_p50: float | None = None


class Estimate(BaseModel):
    job_type: JobType
    cost_range: CostRange
    confidence: str  # 'low' | 'medium' | 'high' — deterministic, from sample size
    n_comparables: int
    building: BuildingCharacteristics
    clarifying_questions: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


# --- Stage 5: quote extraction --------------------------------------------
class QuoteLineItem(BaseModel):
    description: str | None = None
    material_spec_tier: str | None = None
    quantity: float | None = None
    unit_cost: float | None = None
    amount: float | None = None


class QuoteRecord(BaseModel):
    """Structured contractor quote. The figures here are TRANSCRIBED from the PDF
    (stated values), not estimated by the model."""

    contractor_name: str | None = None
    job_type: JobType = JobType.OTHER
    address: str | None = None
    quote_date: str | None = None
    line_items: list[QuoteLineItem] = Field(default_factory=list)
    labor_hours: float | None = None
    labor_rate: float | None = None
    soft_costs: float | None = None
    total: float | None = None
