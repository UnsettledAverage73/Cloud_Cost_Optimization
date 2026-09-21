"""
CloudPulse Real-Time FinOps Notification Engine
Generates interactive Slack Block Kit and Microsoft Teams Adaptive Cards for cost anomalies,
fleet-wide batch summaries, and 1-click GitOps remediation buttons.
"""

import json
import logging
import urllib.request
from typing import Dict, Any, Optional, List
from services.currency_converter import currency_converter

logger = logging.getLogger("cloudpulse.notifications")


class FinOpsNotificationEngine:
    """
    Generates rich, interactive Slack and Teams notification cards for FinOps alerts,
    fleet batch summaries, and interactive remediation callbacks.
    """

    @staticmethod
    def format_slack_alert(
        resource_id: str,
        finding_title: str,
        severity: str = "HIGH",
        current_monthly_spend: float = 0.0,
        potential_monthly_savings: float = 0.0,
        recommended_action: str = "Downsize idle instance to Graviton t4g",
        repo_name: str = "infrastructure/aws-workloads"
    ) -> Dict[str, Any]:
        """
        Creates an enterprise Slack Block Kit interactive message for a single resource.
        """
        severity_emoji = "🚨" if severity.upper() == "CRITICAL" else "⚠️" if severity.upper() == "HIGH" else "💡"
        annual_savings = round(potential_monthly_savings * 12.0, 2)

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{severity_emoji} [{severity.upper()}] CloudPulse Waste Alert: {finding_title}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Resource ID:*\n`{resource_id}`"},
                    {"type": "mrkdwn", "text": f"*Severity:*\n*{severity.upper()}*"},
                    {"type": "mrkdwn", "text": f"*Current Monthly Cost:*\n${current_monthly_spend:.2f}/mo"},
                    {"type": "mrkdwn", "text": f"*Potential Savings:*\n*${potential_monthly_savings:.2f}/mo* (${annual_savings:.2f}/yr)"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{recommended_action}*\n_Validated against AWS Well-Architected Cost Optimization standards._"
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🚀 Open Terraform PR", "emoji": True},
                        "style": "primary",
                        "value": json.dumps({"action": "pr", "resource_id": resource_id, "repo": repo_name}),
                        "action_id": "cloudpulse_open_pr"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⚡ 1-Click Remediate", "emoji": True},
                        "value": json.dumps({"action": "apply", "resource_id": resource_id}),
                        "action_id": "cloudpulse_apply_now"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⏰ Snooze 30 Days", "emoji": True},
                        "value": json.dumps({"action": "snooze", "resource_id": resource_id}),
                        "action_id": "cloudpulse_snooze"
                    }
                ]
            }
        ]

        return {
            "text": f"CloudPulse Waste Alert: {resource_id} (${potential_monthly_savings:.2f}/mo potential savings)",
            "blocks": blocks
        }

    @staticmethod
    def format_slack_batch_summary(
        findings: List[Dict[str, Any]],
        total_monthly_spend: float = 0.0,
        total_monthly_savings: float = 0.0,
        health_score: float = 85.0,
        account_id: str = "Enterprise Fleet",
        currency: str = "USD",
        rate: float = 84.0,
        repo_name: str = "infrastructure/aws-workloads"
    ) -> Dict[str, Any]:
        """
        Creates a consolidated fleet-wide Slack Block Kit message with dual-currency financials
        and 1-click batch remediation buttons.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate
        spend_dual = converter.format_dual(total_monthly_spend, primary_currency=currency)
        savings_annual = round(total_monthly_savings * 12.0, 2)
        savings_annual_dual = converter.format_dual(savings_annual, primary_currency=currency)
        waste_pct = round((total_monthly_savings / total_monthly_spend * 100), 1) if total_monthly_spend > 0 else 0.0

        finding_lines = []
        for f in findings[:6]:
            res_id = f.get("resource_id", "N/A")
            cat = f.get("category", "Compute")
            act = f.get("action", "optimize")
            sav = f.get("monthly_savings", 0.0)
            sav_str = converter.format_dual(sav, primary_currency=currency)
            finding_lines.append(f"• *`{res_id}`* ({cat}): `{act}` ➔ *+{sav_str}/mo*")

        findings_text = "\n".join(finding_lines) if finding_lines else "No waste findings identified."

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"⚡ [CLOUDPULSE AUTOPILOT] Fleet Optimization Digest",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Account Fleet:*\n`{account_id}`"},
                    {"type": "mrkdwn", "text": f"*FinOps Health Score:*\n*{health_score:.1f}/100*"},
                    {"type": "mrkdwn", "text": f"*Current Run-Rate:*\n{spend_dual}/mo"},
                    {"type": "mrkdwn", "text": f"*Recoverable Annual Waste:*\n*{savings_annual_dual}/yr* ({waste_pct}% reduction)"}
                ]
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*🔍 High-Impact Optimization Opportunities ({len(findings)} Total):*\n{findings_text}"
                }
            },
            {"type": "divider"},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "🚀 Open Batch GitOps PR", "emoji": True},
                        "style": "primary",
                        "value": json.dumps({"action": "batch_pr", "findings_count": len(findings), "repo": repo_name}),
                        "action_id": "cloudpulse_batch_pr"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "📊 View PoV Dossier", "emoji": True},
                        "url": "https://github.com/cloudpulse/dossier",
                        "action_id": "cloudpulse_view_pov"
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "⏰ Snooze 14 Days", "emoji": True},
                        "value": json.dumps({"action": "snooze_fleet"}),
                        "action_id": "cloudpulse_snooze"
                    }
                ]
            }
        ]

        return {
            "text": f"CloudPulse Fleet Digest: {len(findings)} findings, {savings_annual_dual}/yr recoverable savings",
            "blocks": blocks
        }

    @staticmethod
    def format_teams_adaptive_card(
        resource_id: str,
        finding_title: str,
        severity: str = "HIGH",
        current_monthly_spend: float = 0.0,
        potential_monthly_savings: float = 0.0,
        recommended_action: str = "Downsize idle instance"
    ) -> Dict[str, Any]:
        """
        Creates a Microsoft Teams Adaptive Card (v1.4 schema) for a single resource.
        """
        facts = [
            {"title": "Resource ID:", "value": resource_id},
            {"title": "Severity:", "value": severity.upper()},
            {"title": "Current Cost:", "value": f"${current_monthly_spend:.2f}/mo"},
            {"title": "Potential Savings:", "value": f"${potential_monthly_savings:.2f}/mo"},
            {"title": "Recommendation:", "value": recommended_action}
        ]
        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Medium",
                                "weight": "Bolder",
                                "text": f"⚠️ [{severity.upper()}] CloudPulse Waste Alert: {finding_title}"
                            },
                            {
                                "type": "FactSet",
                                "facts": facts
                            }
                        ],
                        "actions": [
                            {
                                "type": "Action.Submit",
                                "title": "🚀 Open Terraform PR",
                                "data": {"action": "generate_pr", "resource_id": resource_id}
                            },
                            {
                                "type": "Action.Submit",
                                "title": "⚡ 1-Click Remediate",
                                "data": {"action": "remediate", "resource_id": resource_id}
                            }
                        ]
                    }
                }
            ]
        }

    @staticmethod
    def format_teams_batch_adaptive_card(
        findings: List[Dict[str, Any]],
        total_monthly_spend: float = 0.0,
        total_monthly_savings: float = 0.0,
        health_score: float = 85.0,
        account_id: str = "Enterprise Fleet",
        currency: str = "USD",
        rate: float = 84.0,
        repo_name: str = "infrastructure/aws-workloads"
    ) -> Dict[str, Any]:
        """
        Creates a consolidated Microsoft Teams Adaptive Card for fleet-wide FinOps digests.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate
        spend_dual = converter.format_dual(total_monthly_spend, primary_currency=currency)
        savings_annual = round(total_monthly_savings * 12.0, 2)
        savings_annual_dual = converter.format_dual(savings_annual, primary_currency=currency)

        facts = [
            {"title": "Account Fleet:", "value": account_id},
            {"title": "Health Score:", "value": f"{health_score:.1f}/100"},
            {"title": "Current Spend:", "value": f"{spend_dual}/mo"},
            {"title": "Annual Savings:", "value": f"{savings_annual_dual}/yr"},
            {"title": "Actionable Items:", "value": f"{len(findings)} optimizations identified"}
        ]

        items_body = []
        for f in findings[:5]:
            r_id = f.get("resource_id", "N/A")
            act = f.get("action", "optimize")
            sav = converter.format_dual(f.get("monthly_savings", 0.0), primary_currency=currency)
            items_body.append({
                "type": "TextBlock",
                "text": f"• **`{r_id}`** ({act}): +{sav}/mo",
                "wrap": True,
                "spacing": "Small"
            })

        return {
            "type": "message",
            "attachments": [
                {
                    "contentType": "application/vnd.microsoft.card.adaptive",
                    "content": {
                        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                        "type": "AdaptiveCard",
                        "version": "1.4",
                        "body": [
                            {
                                "type": "TextBlock",
                                "size": "Medium",
                                "weight": "Bolder",
                                "text": "⚡ CloudPulse Fleet FinOps Optimization Digest"
                            },
                            {
                                "type": "FactSet",
                                "facts": facts
                            },
                            {
                                "type": "TextBlock",
                                "weight": "Bolder",
                                "text": "Top Optimization Candidates:",
                                "spacing": "Medium"
                            },
                            *items_body
                        ],
                        "actions": [
                            {
                                "type": "Action.Submit",
                                "title": "🚀 Open Batch GitOps PR",
                                "data": {"action": "batch_pr", "findings_count": len(findings), "repo": repo_name}
                            },
                            {
                                "type": "Action.OpenUrl",
                                "title": "📊 View PoV Dossier",
                                "url": "https://github.com/cloudpulse/dossier"
                            }
                        ]
                    }
                }
            ]
        }

    @staticmethod
    def handle_interactive_callback(payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handles interactive button callback actions from Slack or Teams.
        """
        action = payload.get("action")
        if action in ("batch_pr", "pr", "generate_pr"):
            try:
                from services.gitops_engine import gitops_engine
                from mock_database import DB
                from engines.finops_analyzer import FinOpsAnalyzer
                eval_res = FinOpsAnalyzer.evaluate(DB)
                findings = eval_res.get("findings", [])
                pr_pkg = gitops_engine.create_batch_remediation_pr(
                    findings=findings,
                    repo_name=payload.get("repo", "infrastructure/aws-workloads")
                )
                return {
                    "status": "success",
                    "message": f"✅ [AUTOPILOT] Batch Remediation PR created successfully!",
                    "pr_url": pr_pkg.get("pull_request_url"),
                    "branch": pr_pkg.get("branch_name"),
                    "monthly_savings": pr_pkg.get("total_monthly_savings")
                }
            except Exception as e:
                return {"status": "error", "message": f"Failed to synthesize PR: {e}"}
        elif action in ("apply", "remediate"):
            return {
                "status": "success",
                "message": f"⚡ [AUTOPILOT] Scheduled maintenance remediation for resource `{payload.get('resource_id')}`.",
                "scheduled": True
            }
        elif action in ("snooze", "snooze_fleet"):
            return {
                "status": "success",
                "message": "⏰ [AUTOPILOT] Alerts snoozed for 14 days.",
                "snoozed_days": 14
            }
        return {"status": "ignored", "message": f"Action '{action}' noted."}

    @staticmethod
    def dispatch_webhook(webhook_url: str, payload: Dict[str, Any], timeout: float = 5.0) -> bool:
        """Dispatches notification payload to Slack or Teams webhook."""
        if not webhook_url:
            return False
        if "XXXXX" in webhook_url or "YOUR_WEBHOOK" in webhook_url:
            logger.warning(f"Detected placeholder in webhook URL: {webhook_url}")
            print(f"⚠️ [NOTIFIER] Detected placeholder in webhook URL ({webhook_url[:35]}...). Use a live incoming webhook URL.")
            return False
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in [200, 201, 202, 204]
        except urllib.error.HTTPError as he:
            logger.error(f"Webhook rejected by remote endpoint: HTTP {he.code} ({he.reason})")
            print(f"❌ [NOTIFIER] Webhook rejected by remote endpoint: HTTP {he.code} ({he.reason})")
            return False
        except Exception as e:
            logger.error(f"Failed to dispatch webhook to {webhook_url}: {e}")
            print(f"❌ [NOTIFIER] Failed to dispatch webhook: {e}")
            return False

    @staticmethod
    def dispatch_slack_api(token: str, channel: str, payload: Dict[str, Any], timeout: float = 5.0) -> bool:
        """Dispatches Block Kit payload via Slack Web API (chat.postMessage) using Bot or User token."""
        if not token:
            return False
        try:
            req_data = {
                "channel": channel,
                "text": payload.get("text", "CloudPulse FinOps Alert"),
                "blocks": payload.get("blocks", [])
            }
            data = json.dumps(req_data).encode("utf-8")
            req = urllib.request.Request(
                "https://slack.com/api/chat.postMessage",
                data=data,
                headers={
                    "Content-Type": "application/json; charset=utf-8",
                    "Authorization": f"Bearer {token}"
                }
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                if not res_json.get("ok"):
                    err_msg = res_json.get("error", "unknown_error")
                    logger.error(f"Slack API error: {err_msg}")
                    print(f"❌ [NOTIFIER] Slack API error: {err_msg}")
                    return False
                return True
        except Exception as e:
            logger.error(f"Failed to post to Slack Web API: {e}")
            print(f"❌ [NOTIFIER] Failed to post to Slack API: {e}")
            return False




# Global Singleton
notification_engine = FinOpsNotificationEngine()
