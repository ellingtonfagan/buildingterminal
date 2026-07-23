"""The fixed job taxonomy for v0. Deliberately small — 3-5 job types, not forty.

Anything the classifier cannot confidently map lands in OTHER. A validation step
rejects any label that is not one of these values.
"""

from __future__ import annotations

from enum import Enum


class JobType(str, Enum):
    HEATING_REPLACEMENT = "heating_system_replacement"
    ROOF = "roof_replacement_or_recoat"
    FACADE = "facade_repair_ll11"            # FISP / Local Law 11
    PLUMBING_RISER = "plumbing_riser_replacement"
    ELECTRICAL_UPGRADE = "electrical_service_upgrade"
    INTERIOR_RENO = "general_interior_renovation"
    OTHER = "other_unclassifiable"


TAXONOMY_VALUES: list[str] = [t.value for t in JobType]

# Human-readable descriptions given to the LLM so it maps consistently.
TAXONOMY_DESCRIPTIONS: dict[str, str] = {
    JobType.HEATING_REPLACEMENT.value: "Replacing a boiler, burner, heating system, or hot-water heating plant.",
    JobType.ROOF.value: "Roof replacement, re-roofing, roof recoat, or roof membrane/waterproofing work.",
    JobType.FACADE.value: "Facade / exterior wall repair, pointing, parapet, or FISP / Local Law 11 compliance work.",
    JobType.PLUMBING_RISER.value: "Replacing plumbing risers, water/waste/gas risers, or building-wide piping.",
    JobType.ELECTRICAL_UPGRADE.value: "Upgrading electrical service, service entrance, meters, or increasing amperage.",
    JobType.INTERIOR_RENO.value: "General interior apartment/common-area renovation not covered by a more specific type.",
    JobType.OTHER.value: "Anything that does not clearly fit one of the above, or is too vague to classify.",
}


def is_valid(value: str) -> bool:
    return value in set(TAXONOMY_VALUES)


def coerce(value: str) -> JobType:
    """Return the JobType for a value, or raise. Used by the validation step to
    reject off-taxonomy model output."""
    if not is_valid(value):
        raise ValueError(f"off-taxonomy label: {value!r}")
    return JobType(value)
