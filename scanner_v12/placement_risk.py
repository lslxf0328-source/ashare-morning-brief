"""
V1.2 定增风险分级模块

等级：
A 高风险 >=70
B 中风险 40-69
C 低风险 <40
UNKNOWN 信息不足

说明：
不直接决定买卖，仅作为综合审核字段。
"""


def assess_placement_risk(info=None):

    if info is None:
        info = {}

    score = 0
    reasons = []

    status = info.get("状态", "")
    valid = info.get("公告合格", False)

    # 信息不足
    if not valid:
        return {
            "placement_risk_level": "UNKNOWN",
            "placement_risk_score": None,
            "placement_risk_reason": "定增公告未完成有效核验"
        }


    # 已确认存在风险状态

    if status in ["风险", "否决", "高风险"]:
        score += 80
        reasons.append("定增事项存在明确风险")

    elif status in ["观察", "中风险"]:
        score += 50
        reasons.append("定增事项需要持续观察")

    elif status in ["通过", "低风险"]:
        score += 10
        reasons.append("定增风险较低")

    else:
        score += 40
        reasons.append("定增状态未知")


    if score >= 70:
        level = "A"

    elif score >= 40:
        level = "B"

    else:
        level = "C"


    return {
        "placement_risk_level": level,
        "placement_risk_score": score,
        "placement_risk_reason": ";".join(reasons)
    }
