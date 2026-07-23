from cost_engine.costmodel.cost_index import normalize, year_from_date


def test_normalize_scales_older_dollars_up():
    # An older year has a lower index, so its dollars should scale UP to base year.
    assert normalize(100.0, 2015) > 100.0


def test_normalize_base_year_is_identity():
    assert normalize(100.0, 2026, base_year=2026) == 100.0


def test_normalize_monotonic_in_year():
    # More recent year => smaller uplift.
    older = normalize(100.0, 2010)
    newer = normalize(100.0, 2022)
    assert older > newer > 100.0


def test_normalize_clamps_out_of_range_years():
    # Years outside the table clamp to the nearest endpoint rather than crash.
    assert normalize(100.0, 1990) == normalize(100.0, 2005)
    assert normalize(100.0, 2050) == normalize(100.0, 2026)


def test_year_from_date():
    assert year_from_date("2019-05-01T00:00:00") == 2019
    assert year_from_date("05/12/2021") == 2021
    assert year_from_date("") is None
    assert year_from_date(None) is None
