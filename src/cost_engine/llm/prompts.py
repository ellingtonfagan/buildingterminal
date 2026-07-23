"""Versioned prompt registry.

Every prompt has an explicit version string that is logged with each LLM call
and each eval run, so prompt versions can be compared over time. Bump the version
whenever the text changes.
"""

from __future__ import annotations

from ..classify.taxonomy import TAXONOMY_DESCRIPTIONS, TAXONOMY_VALUES

CLASSIFIER_PROMPT_VERSION = "classifier-v1"
JOBSPEC_PROMPT_VERSION = "jobspec-v1"
QUOTE_PROMPT_VERSION = "quote-v1"


def _taxonomy_block() -> str:
    lines = [f"- {v}: {TAXONOMY_DESCRIPTIONS[v]}" for v in TAXONOMY_VALUES]
    return "\n".join(lines)


def classifier_system() -> str:
    return (
        "You classify NYC Department of Buildings work descriptions into a FIXED "
        "taxonomy. The descriptions are inconsistent free text. Choose exactly one "
        "job type. If the description is vague or does not clearly fit a specific "
        "type, choose 'other_unclassifiable'. Do NOT invent labels outside the "
        "taxonomy. Do NOT output any numbers, costs, or confidence scores.\n\n"
        "Taxonomy:\n" + _taxonomy_block()
    )


def classifier_user(work_description: str) -> str:
    return f"Work description:\n{work_description.strip()}\n\nClassify it."


def jobspec_system() -> str:
    return (
        "You convert a plain-language description of a NYC building job into a "
        "structured spec. Choose one job type from the taxonomy. Extract concrete "
        "scope indicators (e.g. 'full roof tear-off', 'gas riser', 'parapet "
        "rebuild'). List any missing information a contractor would need to price "
        "the job (e.g. number of stories, square footage, material tier). "
        "IMPORTANT: never mention, estimate, or output any dollar figure or cost — "
        "you only structure the request.\n\n"
        "Taxonomy:\n" + _taxonomy_block()
    )


def jobspec_user(job_description: str) -> str:
    return f"Job description:\n{job_description.strip()}\n\nStructure it."


def quote_system() -> str:
    return (
        "You extract a structured record from a contractor quote for NYC building "
        "work. Transcribe values that are STATED in the document — do not estimate "
        "or invent figures; leave a field null if the quote does not state it. Map "
        "the job to one taxonomy type. Capture line items with material spec tier "
        "where stated, labor hours and rate where stated, soft costs, and the "
        "total.\n\nTaxonomy:\n" + _taxonomy_block()
    )


def quote_user(pdf_text: str) -> str:
    return f"Contractor quote text:\n{pdf_text.strip()}\n\nExtract the structured record."
