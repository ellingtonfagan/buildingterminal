"""Stage 4 — LLM structures a plain-language job description into a JobSpec.

The LLM in this path NEVER sees or produces a dollar figure. It only chooses a
taxonomy job type, extracts scope indicators, and lists missing-info questions.
Every cost is produced later by the deterministic model.
"""

from __future__ import annotations

from ..config import CONFIG
from ..llm.prompts import JOBSPEC_PROMPT_VERSION, jobspec_system, jobspec_user
from ..models import JobSpec
from ..classify.taxonomy import JobType, coerce


def structure_job(job_description: str) -> JobSpec:
    text = (job_description or "").strip()
    if not text:
        return JobSpec(job_type=JobType.OTHER, missing_info_questions=["What work is being done?"])

    # Offline dev aid mirrors the classifier's fallback so the endpoint works
    # without a key. Not a substitute for the LLM.
    if CONFIG.allow_heuristic_fallback and not CONFIG.anthropic_api_key:
        from ..classify.classifier import classify

        job_type = classify(text).job_type
        return JobSpec(
            job_type=job_type,
            scope_indicators=[],
            missing_info_questions=[
                "How many stories is the building?",
                "What is the approximate square footage?",
                "What material/spec tier is expected?",
            ],
        )

    from ..llm.client import structured_call

    spec = structured_call(
        model=CONFIG.jobspec_model,
        system=jobspec_system(),
        user=jobspec_user(text),
        response_model=JobSpec,
        prompt_version=JOBSPEC_PROMPT_VERSION,
    )
    coerce(spec.job_type.value)  # reject off-taxonomy
    return spec
