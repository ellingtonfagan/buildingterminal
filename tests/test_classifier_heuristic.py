"""The offline keyword heuristic is a dev aid only, but it is deterministic and
worth pinning so the offline pipeline stays predictable."""

from cost_engine.classify.classifier import _heuristic
from cost_engine.classify.taxonomy import JobType


def test_heuristic_maps_common_descriptions():
    assert _heuristic("REPLACE GAS FIRED BOILER").job_type is JobType.HEATING_REPLACEMENT
    assert _heuristic("NEW ROOFING MEMBRANE AT MAIN ROOF").job_type is JobType.ROOF
    assert _heuristic("REPOINT BRICK FACADE PER LL11").job_type is JobType.FACADE
    assert _heuristic("REPLACE WATER RISERS").job_type is JobType.PLUMBING_RISER
    assert _heuristic("UPGRADE ELECTRICAL SERVICE TO 400A").job_type is JobType.ELECTRICAL_UPGRADE
    assert _heuristic("GUT RENOVATION OF APARTMENT").job_type is JobType.INTERIOR_RENO


def test_heuristic_defaults_to_other():
    assert _heuristic("MISC WORK PER PLANS").job_type is JobType.OTHER
