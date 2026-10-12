"""A股 V1.2 定增风险分级模块。

将原有定增一票否决升级为风险分层：
A >=70 高风险排除；B 40-69 降权观察；C 0-39 正常通过；未知待核实。
"""

from dataclasses import dataclass


@dataclass
class PlacementRiskResult:
    level: str
    score: int
    reason: str


def assess_placement_risk(info: dict) -> dict:
    """根据公告核验信息计算定增风险。

    info字段均允许缺失。缺少关键公告信息时返回未知，不自动推荐。
    """
    if not info or info.get("announcement_available") is False:
        return {"placement_risk_level": "未知", "placement_risk_score": None,
                "placement_risk_reason": "公告信息不足，待核实"}

    score = 0
    reasons = []

    high_items = [
        ("has_current_plan", 25, "当前存在定增预案"),
        ("under_review", 20, "定增审核中"),
        ("major_holder_arbitrage", 15, "大股东参与套利倾向"),
        ("high_discount", 10, "高折价发行"),
        ("unclear_usage", 10, "募资用途不明确"),
        ("frequent_financing", 10, "短期频繁融资"),
    ]
    medium_items = [
        ("lockup_pressure", 10, "已完成定增但存在限售压力"),
        ("expansion_not_verified", 8, "募资扩产尚未验证"),
        ("large_ratio", 8, "定增比例较高"),
    ]

    for key, weight, text in high_items + medium_items:
        if info.get(key):
            score += weight
            reasons.append(text)

    if score >= 70:
        level = "A"
    elif score >= 40:
        level = "B"
    else:
        level = "C"

    return {
        "placement_risk_level": level,
        "placement_risk_score": score,
        "placement_risk_reason": "；".join(reasons) if reasons else "未发现明显定增风险",
    }
