import json
import os
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional

class FinOpsNotifier:
    """
    Multi-channel notification dispatcher supporting Slack Webhooks and Twilio WhatsApp escalation.
    """

    def __init__(self, slack_webhook_url: Optional[str] = None):
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.whatsapp_recipient = os.getenv("WHATSAPP_ALERT_TO")

    def format_slack_payload(self, findings: List[Dict[str, Any]], monthly_cost: float, health_score: float) -> Dict[str, Any]:
        """Formats findings into a rich Slack Block Kit layout."""
        critical_count = sum(1 for f in findings if f.get("severity") == "CRITICAL")
        total_savings = sum(float(f.get("savings", f.get("monthly_savings", 0))) for f in findings)

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "CloudPulse FinOps & Security Alert", "emoji": True}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*FinOps Health Score:*\n{health_score}/100"},
                    {"type": "mrkdwn", "text": f"*Estimated Monthly Spend:*\n${monthly_cost:,.2f}"},
                    {"type": "mrkdwn", "text": f"*Potential Savings:*\n${total_savings:,.2f}/mo"},
                    {"type": "mrkdwn", "text": f"*Critical Vulnerabilities:*\n{critical_count}"}
                ]
            },
            {"type": "divider"}
        ]

        top_findings = findings[:5]
        for f in top_findings:
            sev = f.get("severity", "MEDIUM")
            emoji = ":rotating_light:" if sev == "CRITICAL" else ":warning:" if sev == "HIGH" else ":information_source:"
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *[{sev}] {f.get('title', f.get('message', 'Issue'))}*\nResource: `{f.get('resource_id', 'N/A')}` | Est. Savings: *${float(f.get('savings', 0)):.2f}/mo*"
                }
            })

        return {"blocks": blocks}

    def send_slack_alert(self, findings: List[Dict[str, Any]], monthly_cost: float = 0.0, health_score: float = 85.0) -> bool:
        if not self.slack_webhook_url:
            print("⚠️ [NOTIFIER] Slack webhook URL not configured.")
            return False

        payload = self.format_slack_payload(findings, monthly_cost, health_score)
        try:
            req = urllib.request.Request(
                self.slack_webhook_url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status in (200, 204)
        except Exception as e:
            print(f"❌ [NOTIFIER] Failed to send Slack alert: {e}")
            return False

    def send_whatsapp_alert(self, title: str, message: str, to_number: Optional[str] = None) -> bool:
        recipient = to_number or self.whatsapp_recipient
        if not (self.twilio_sid and self.twilio_auth_token and recipient):
            print("⚠️ [NOTIFIER] WhatsApp Twilio credentials not configured.")
            return False

        try:
            from twilio.rest import Client
            client = Client(self.twilio_sid, self.twilio_auth_token)
            body = f"🚨 *CloudPulse FinOps Alert*\n\n*{title}*\n{message}\n\nLogin to dashboard for 1-click remediation."
            msg = client.messages.create(
                from_=self.twilio_whatsapp_from,
                to=f"whatsapp:{recipient}" if not recipient.startswith("whatsapp:") else recipient,
                body=body
            )
            return bool(msg.sid)
        except Exception as e:
            print(f"❌ [NOTIFIER] Failed to dispatch WhatsApp alert: {e}")
            return False
