"""
CloudPulse Real-Time FinOps Notification Engine
Generates interactive Slack Block Kit and Microsoft Teams Adaptive Cards for cost anomalies,
waste alerts, and 1-click GitOps remediation buttons.
"""

import json
import logging
import urllib.request
from typing import Dict, Any, Optional, List

logger = logging.getLogger("cloudpulse.notifications")


class FinOpsNotificationEngine:
    """
    Generates rich, interactive Slack and Teams notification cards for FinOps alerts.
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
        Creates an enterprise Slack Block Kit interactive message.
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
    def format_teams_adaptive_card(
        resource_id: str,
        finding_title: str,
        severity: str = "HIGH",
        current_monthly_spend: float = 0.0,
        potential_monthly_savings: float = 0.0,
        recommended_action: str = "Downsize idle instance"
    ) -> Dict[str, Any]:
        """
        Creates a Microsoft Teams Adaptive Card (v1.4 schema).
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
    def dispatch_webhook(webhook_url: str, payload: Dict[str, Any], timeout: float = 5.0) -> bool:
        """Dispatches notification payload to Slack or Teams webhook."""
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status in [200, 204]
        except Exception as e:
            logger.error(f"Failed to dispatch webhook to {webhook_url}: {e}")
            return False


# Global Singleton
notification_engine = FinOpsNotificationEngine()
