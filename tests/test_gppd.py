from energy_intelligence.gppd import normalize_name


def test_normalize_name_strips_boilerplate():
    assert normalize_name("Ang Thong Solar Power Plant") == normalize_name("Ang Thong")
