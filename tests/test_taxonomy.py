import pytest

from cost_engine.classify.taxonomy import (
    TAXONOMY_VALUES,
    JobType,
    coerce,
    is_valid,
)


def test_taxonomy_has_seven_types():
    assert len(TAXONOMY_VALUES) == 7
    assert "other_unclassifiable" in TAXONOMY_VALUES


def test_is_valid():
    assert is_valid("roof_replacement_or_recoat")
    assert not is_valid("plumbing")  # off-taxonomy


def test_coerce_rejects_off_taxonomy():
    assert coerce("facade_repair_ll11") is JobType.FACADE
    with pytest.raises(ValueError):
        coerce("kitchen_remodel")
