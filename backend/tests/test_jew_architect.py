import pytest
from backend.copilot.decision_engine import SemIfDecisionEngine, JevDecisionEngine, get_decision_engine, ARCHITECT_DECISION_CANDIDATES
from backend.copilot.jew_architect import JewSystemArchitect

def test_semif_decision_engine_graviton_routing():
    engine = SemIfDecisionEngine()
    res = engine.decide(
        user_intent="Compare m5.2xlarge with Graviton pricing",
        cloud_context="Active nodes running in us-east-1"
    )
    assert res.selected_tool == "rate_card_graviton_roi"
    assert res.confidence >= 0.80
    assert "SemIf" in res.decision_provider
    assert len(res.execution_plan) > 0
    assert res.latency_ms > 0

def test_semif_decision_engine_terraform_pr_routing():
    engine = SemIfDecisionEngine()
    res = engine.decide(
        user_intent="Generate a terraform pull request to downsize idle compute",
        cloud_context="Active nodes running in us-east-1"
    )
    assert res.selected_tool == "generate_terraform_pr"
    assert res.confidence >= 0.85
    assert any("Terraform" in step or "HCL" in step for step in res.execution_plan)

def test_semif_decision_engine_forensics_routing():
    engine = SemIfDecisionEngine()
    res = engine.decide(
        user_intent="Why did our compute cost spike on Friday?",
        cloud_context="Active nodes running in us-east-1"
    )
    assert res.selected_tool == "cloudtrail_spike_forensics"
    assert res.confidence >= 0.85

def test_jev_drop_in_compatibility():
    jev = JevDecisionEngine()
    res = jev.decide(
        user_intent="Check SLA safety guardrail before modifying nodes",
        cloud_context="Active nodes running in us-east-1"
    )
    assert res.selected_tool == "sla_safety_guardrail"
    assert res.confidence >= 0.80

def test_jew_architect_end_to_end_chat():
    architect = JewSystemArchitect()
    rep = architect.chat("Compare m5.2xlarge with Graviton pricing")
    assert "answer" in rep
    assert "decision" in rep
    assert rep["decision"]["selected_tool"] == "rate_card_graviton_roi"
    assert rep["tool_called"] == "rate_card_graviton_roi"
    assert "Graviton" in rep["answer"]
    assert len(rep["execution_plan"]) > 0
