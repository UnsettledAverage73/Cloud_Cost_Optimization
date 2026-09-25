"""
CloudPulse Multi-Channel Notifications API Router
Enterprise alerting integration with Slack (Block Kit) and Microsoft Teams (Adaptive Cards),
interactive callback webhooks, and alert routing policies.
"""

import json
from typing import Optional
from fastapi import APIRouter, Request

try:
    from services.notification_engine import notification_engine
    from engines.finops_analyzer import FinOpsAnalyzer
    from core.state import resolve_active_inventory, get_realtime_store
except ImportError:
    from backend.services.notification_engine import notification_engine
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.core.state import resolve_active_inventory, get_realtime_store

router = APIRouter(prefix="/api/v2/notifications", tags=["Multi-Channel Notifications"])


@router.post("/slack")
async def send_slack_finops_alert(payload: dict):
    """Generates and optionally dispatches Slack Block Kit alert."""
    resource_id = payload.get("resource_id", "unknown-resource")
    finding_title = payload.get("finding_title", "Idle Cloud Resource Detected")
    severity = payload.get("severity", "HIGH")
    current_spend = float(payload.get("current_monthly_spend", 0.0))
    savings = float(payload.get("potential_monthly_savings", 0.0))
    action = payload.get("recommended_action", "Downsize or stop resource")
    webhook_url = payload.get("webhook_url")

    card = notification_engine.format_slack_alert(
        resource_id=resource_id,
        finding_title=finding_title,
        severity=severity,
        current_monthly_spend=current_spend,
        potential_monthly_savings=savings,
        recommended_action=action
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@router.post("/teams")
async def send_teams_finops_alert(payload: dict):
    """Generates and optionally dispatches Microsoft Teams Adaptive Card."""
    resource_id = payload.get("resource_id", "unknown-resource")
    finding_title = payload.get("finding_title", "Idle Cloud Resource Detected")
    severity = payload.get("severity", "HIGH")
    savings = float(payload.get("potential_monthly_savings", 0.0))
    action = payload.get("recommended_action", "Downsize or stop resource")
    webhook_url = payload.get("webhook_url")

    card = notification_engine.format_teams_adaptive_card(
        resource_id=resource_id,
        finding_title=finding_title,
        severity=severity,
        potential_monthly_savings=savings,
        recommended_action=action
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@router.post("/slack/batch")
async def send_slack_batch_finops_digest(payload: Optional[dict] = None):
    """Generates and optionally dispatches fleet-wide Slack Block Kit batch digest."""
    payload = payload or {}
    webhook_url = payload.get("webhook_url")
    currency = payload.get("currency", "USD")
    rate = float(payload.get("rate", 84.0))

    inventory = resolve_active_inventory()
    try:
        eval_res = FinOpsAnalyzer.evaluate(inventory)
        findings = payload.get("findings") or eval_res.get("findings", [])
        monthly_spend = eval_res.get("total_monthly_spend", 68.40)
        monthly_savings = eval_res.get("total_potential_monthly_savings", 0.0)
        health_score = eval_res.get("health_score", 85.0)
    except Exception:
        findings = payload.get("findings", [])
        monthly_spend = 68.40
        monthly_savings = 25.0
        health_score = 85.0

    account_id = inventory.get("metadata", {}).get("account_id", "582812122408")

    card = notification_engine.format_slack_batch_summary(
        findings=findings,
        total_monthly_spend=monthly_spend,
        total_monthly_savings=monthly_savings,
        health_score=health_score,
        account_id=account_id,
        currency=currency,
        rate=rate,
        repo_name=payload.get("repo_name", "infrastructure/aws-workloads")
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@router.post("/teams/batch")
async def send_teams_batch_finops_digest(payload: Optional[dict] = None):
    """Generates and optionally dispatches fleet-wide Microsoft Teams Adaptive Card batch digest."""
    payload = payload or {}
    webhook_url = payload.get("webhook_url")
    currency = payload.get("currency", "USD")
    rate = float(payload.get("rate", 84.0))

    inventory = resolve_active_inventory()
    try:
        eval_res = FinOpsAnalyzer.evaluate(inventory)
        findings = payload.get("findings") or eval_res.get("findings", [])
        monthly_spend = eval_res.get("total_monthly_spend", 68.40)
        monthly_savings = eval_res.get("total_potential_monthly_savings", 0.0)
        health_score = eval_res.get("health_score", 85.0)
    except Exception:
        findings = payload.get("findings", [])
        monthly_spend = 68.40
        monthly_savings = 25.0
        health_score = 85.0

    account_id = inventory.get("metadata", {}).get("account_id", "582812122408")

    card = notification_engine.format_teams_batch_adaptive_card(
        findings=findings,
        total_monthly_spend=monthly_spend,
        total_monthly_savings=monthly_savings,
        health_score=health_score,
        account_id=account_id,
        currency=currency,
        rate=rate,
        repo_name=payload.get("repo_name", "infrastructure/aws-workloads")
    )

    dispatched = False
    if webhook_url:
        dispatched = notification_engine.dispatch_webhook(webhook_url, card)

    return {"status": "success", "dispatched": dispatched, "payload": card}


@router.get("/config")
async def get_notification_config():
    """Returns active notification channels, webhooks, and alert routing policies."""
    return notification_engine.get_config()


@router.post("/config")
async def update_notification_config(payload: dict):
    """Updates and persists multi-channel notification settings."""
    updated = notification_engine.update_config(payload)
    meta = get_realtime_store().setdefault("metadata", {})
    if "slack_webhook_url" in updated:
        meta["slack_webhook_url"] = updated["slack_webhook_url"]
    if "teams_webhook_url" in updated:
        meta["teams_webhook_url"] = updated["teams_webhook_url"]
    if "slack_channel" in updated:
        meta["slack_channel"] = updated["slack_channel"]
    return updated


@router.get("/history")
async def get_notification_history(limit: int = 50):
    """Returns audit log of all notification deliveries and statuses."""
    return {"count": len(notification_engine.get_history(limit)), "history": notification_engine.get_history(limit)}


@router.post("/test")
async def test_notification_channels(payload: Optional[dict] = None):
    """Sends a live test notification card to Slack and/or Microsoft Teams."""
    payload = payload or {}
    channels = payload.get("channels")
    if not channels and payload.get("channel"):
        channels = [payload.get("channel")]
    res = notification_engine.dispatch_event("test", {}, channels=channels)
    return res


@router.post("/dispatch")
async def dispatch_notification_event(payload: dict):
    """Universal notification dispatcher routing alerts across all CloudPulse functionalities."""
    event_type = payload.get("event_type", "waste_alert")
    data = payload.get("data", payload)
    channels = payload.get("channels")
    res = notification_engine.dispatch_event(event_type, data, channels=channels)
    return res


@router.post("/anomaly")
async def send_anomaly_notification(payload: dict):
    """Generates and dispatches spend anomaly alerts to Slack and Teams."""
    res = notification_engine.dispatch_event("anomaly", payload)
    return res


@router.post("/grace-period")
async def send_grace_period_notification(payload: dict):
    """Generates and dispatches 10-minute scheduler grace period alert."""
    res = notification_engine.dispatch_event("grace_period", payload)
    return res


@router.post("/sla")
async def send_sla_breach_notification(payload: dict):
    """Generates and dispatches post-remediation SLA breach alert."""
    res = notification_engine.dispatch_event("sla_breach", payload)
    return res


@router.post("/interactive/callback")
async def handle_notification_interactive_callback(request: Request):
    """Receives interactive button action callbacks from Slack / Teams."""
    content_type = request.headers.get("content-type", "")
    if "application/x-www-form-urlencoded" in content_type:
        form_data = await request.form()
        payload_raw = form_data.get("payload")
        if payload_raw:
            try:
                payload = json.loads(payload_raw)
            except Exception:
                payload = {"payload": payload_raw}
        else:
            payload = dict(form_data)
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    result = notification_engine.handle_interactive_callback(payload)
    return result
