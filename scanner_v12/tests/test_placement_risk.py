from scanner_v12.placement_risk import assess_placement_risk


def test_high_risk():
    result = assess_placement_risk({
        "announcement_available": True,
        "has_current_plan": True,
        "under_review": True,
        "major_holder_arbitrage": True,
        "high_discount": True,
    })
    assert result["placement_risk_level"] == "A"


def test_no_placement_risk():
    result = assess_placement_risk({"announcement_available": True})
    assert result["placement_risk_level"] == "C"


def test_unknown():
    result = assess_placement_risk({"announcement_available": False})
    assert result["placement_risk_level"] == "未知"
