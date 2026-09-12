"""Shared deterministic task classification for state, CLI and Dashboard."""

PASSIVE_CLASSES = {
    "market_data_unavailable": "system_data_issue",
    "financial_data_unavailable": "system_data_issue",
    "financial_definition_missing": "definition_gap",
    "evidence_not_available": "waiting_evidence",
    "holding_event_identity_unverified": "system_data_issue",
}
LABELS = {
    "research_now": "现在需要研究", "human_decision": "需要人工决定",
    "system_data_issue": "系统数据故障", "definition_gap": "缺少规则定义",
    "waiting_evidence": "等待未来披露", "none": "继续观察",
}


def classify(guidance: dict) -> dict:
    blocker = guidance.get("blocker_code")
    skills = guidance.get("recommended_skill") or []
    if blocker in PASSIVE_CLASSES:
        category = PASSIVE_CLASSES[blocker]
    elif guidance.get("requires_user_action") is True:
        category = "research_now" if skills else "human_decision"
    else:
        category = "none"
    status = {
        "definition_gap": "WAITING_RULE_DEFINITION",
        "waiting_evidence": "WAITING_EVIDENCE",
        "system_data_issue": "SYSTEM_DATA_ISSUE",
        "human_decision": "READY_FOR_USER_DISPOSITION",
        "none": "MONITORING",
    }.get(category)
    if category == "research_now":
        status = "READY_FOR_" + str(skills[0]).replace("-", "_").upper()
    return {"task_class": category, "task_label": LABELS[category], "workflow_status": status}
