"""
Test suite validating Copilot tool schemas, function calling specifications,
dynamic parameter extraction, and simulation isolation.
"""

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from copilot.tools.schemas import (
    TOOL_DEFINITIONS,
    PricingLookupInput,
    CloudTrailForensicsInput,
    SQLAnalyticsInput,
    TerraformPRInput
)
from copilot.agent import FinOpsAutonomousCopilot
from copilot.tools.cloudtrail_forensics_tool import investigate_event_spikes


def test_tool_definitions_spec():
    """Verify that all tools have valid OpenAI/Groq function calling schema structure."""
    assert len(TOOL_DEFINITIONS) >= 6
    names = [t["function"]["name"] for t in TOOL_DEFINITIONS]
    assert "pricing_rag" in names
    assert "cloudtrail_forensics" in names
    assert "sql_analytics" in names
    assert "terraform_pr" in names
    assert "kubernetes_allocations" in names
    assert "focus_lakehouse" in names

    for tool in TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_pydantic_schema_validation():
    """Verify Pydantic input schemas enforce types and defaults."""
    # Pricing input
    p_in = PricingLookupInput(resource_type="t3.large")
    assert p_in.resource_type == "t3.large"
    assert p_in.region == "us-east-1"

    # CloudTrail input
    ct_in = CloudTrailForensicsInput()
    assert ct_in.service == "AmazonEC2"
    assert ct_in.hours_back == 168
    assert ct_in.allow_simulation is True

    # SQL analytics input
    sql_in = SQLAnalyticsInput(query="SELECT 1;")
    assert sql_in.query == "SELECT 1;"


def test_dynamic_instance_type_copilot_extraction():
    """Verify Copilot dynamically extracts any valid EC2 instance type instead of hardcoded fallbacks."""
    copilot = FinOpsAutonomousCopilot()

    chat = copilot.chat("Can you check the price of t3.large in us-east-1?")
    assert chat["tool_called"] == "pricing_rag"
    assert "t3.large" in chat["answer"]

    chat2 = copilot.chat("What is the cost of c5.xlarge?")
    assert chat2["tool_called"] == "pricing_rag"
    assert "c5.xlarge" in chat2["answer"]


def test_simulation_flag_isolation():
    """Verify that setting allow_simulation=False returns clean zero-event status when no credentials exist."""
    res = investigate_event_spikes(service="AmazonRDS", allow_simulation=False)
    assert res["is_simulated"] is False
    assert res["matched_events_count"] == 0
    assert res["events"] == []
    assert res["primary_suspect"] is None
    assert res["status"] in ("LIVE_EVENTS_DETECTED", "NO_LIVE_EVENTS")
