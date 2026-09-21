import json
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Any, Optional

# Auto-load local .env if present
for cand in [Path(__file__).resolve().parent / ".env", Path(__file__).resolve().parent.parent / ".env", Path.cwd() / ".env"]:
    if cand.exists():
        try:
            with open(cand, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip().strip("'\"")
        except Exception:
            pass

class FinOpsNotifier:
    """
    Multi-channel notification dispatcher supporting Slack Webhooks and Twilio WhatsApp escalation.
    Supports both Account SID + Auth Token, and API Key SID + Secret authentication.
    """

    def __init__(self, slack_webhook_url: Optional[str] = None):
        self.slack_webhook_url = slack_webhook_url or os.getenv("SLACK_WEBHOOK_URL")
        self.twilio_account_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_auth_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_api_key = os.getenv("TWILIO_API_KEY")
        self.twilio_api_secret = os.getenv("TWILIO_API_SECRET")
        self.twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")
        self.whatsapp_recipient = os.getenv("WHATSAPP_ALERT_TO")

    def _get_twilio_client(self):
        """Constructs Twilio REST Client using configured credentials."""
        from twilio.rest import Client

        # Priority 1: Master Account SID + Auth Token (Canonical Twilio Auth)
        if self.twilio_account_sid and self.twilio_auth_token:
            return Client(self.twilio_account_sid, self.twilio_auth_token)

        # Priority 2: API Key + Secret + Account SID
        if self.twilio_api_key and self.twilio_api_secret:
            if not self.twilio_account_sid:
                print("⚠️ [NOTIFIER] Twilio API Key detected, but TWILIO_ACCOUNT_SID (starts with AC...) is missing.")
                print("   Twilio requires the Account SID to route WhatsApp messages. Add TWILIO_ACCOUNT_SID=AC... to .env")
                return None
            return Client(self.twilio_api_key, self.twilio_api_secret, account_sid=self.twilio_account_sid)

        return None

    def format_slack_payload(self, findings: List[Dict[str, Any]], monthly_cost: float = 0.0, health_score: float = 85.0) -> Dict[str, Any]:
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

    def format_whatsapp_body(self, title: str, message: str) -> str:
        """Formats alert into an enterprise WhatsApp markdown payload."""
        return (
            f"⚡ *CloudPulse AI FinOps Autopilot*\n\n"
            f"🚨 *{title}*\n"
            f"{message}\n\n"
            f"👉 Run `./bin/cloudpulse apply --dry-run` to generate Terraform PR."
        )

    def send_slack_alert(self, findings: List[Dict[str, Any]], monthly_cost: float = 0.0, health_score: float = 85.0) -> bool:
        if not self.slack_webhook_url:
            print("⚠️ [NOTIFIER] Slack webhook URL not configured.")
            return False

        if "XXXXX" in self.slack_webhook_url or "YOUR_WEBHOOK" in self.slack_webhook_url:
            print("⚠️ [NOTIFIER] Detected placeholder in Slack webhook URL.")
            print("   Please provide a live Slack Incoming Webhook (e.g. --webhook https://hooks.slack.com/services/T.../B.../...).")
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
        except urllib.error.HTTPError as err:
            print(f"❌ [NOTIFIER] Slack webhook rejected request: HTTP {err.code} ({err.reason})")
            if err.code == 404:
                print("💡 [SLACK HINT] The Slack webhook URL was not found (404). Verify that the Incoming Webhook is active in your Slack workspace.")
            return False
        except Exception as e:
            print(f"❌ [NOTIFIER] Failed to send Slack alert: {e}")
            return False

    def send_whatsapp_alert(self, title: str, message: str, to_number: Optional[str] = None) -> bool:
        recipient = to_number or self.whatsapp_recipient
        if not recipient:
            print("⚠️ [NOTIFIER] Recipient phone number not specified. Set WHATSAPP_ALERT_TO in .env or pass to_number.")
            return False

        client = self._get_twilio_client()
        if not client:
            print("⚠️ [NOTIFIER] WhatsApp Twilio credentials not configured.")
            return False

        # Ensure correct WhatsApp prefix
        clean_num = recipient.strip()
        if not clean_num.startswith("whatsapp:"):
            if not clean_num.startswith("+"):
                clean_num = f"+{clean_num}"
            target_to = f"whatsapp:{clean_num}"
        else:
            target_to = clean_num

        body = self.format_whatsapp_body(title, message)

        try:
            msg = client.messages.create(
                from_=self.twilio_whatsapp_from,
                to=target_to,
                body=body
            )
            print(f"✅ [NOTIFIER] WhatsApp alert dispatched successfully (SID: {msg.sid})")
            return True
        except Exception as e:
            err_str = str(e)
            print(f"❌ [NOTIFIER] Failed to dispatch WhatsApp alert: {err_str}")
            if "21654" in err_str or "ContentSid Required" in err_str or "63016" in err_str:
                print("💡 [TWILIO WHATSAPP SANDBOX ACTIVATION STEPS]")
                print(f"   Meta/Twilio requires the recipient phone number ({clean_num}) to opt into your Twilio Sandbox first:")
                print("   1. Open WhatsApp on your phone.")
                print("   2. In your Twilio Console -> Messaging -> Try it out -> Send a WhatsApp message, find your join code (e.g. 'join <keyword>').")
                print("   3. Send that code to the Twilio Sandbox number (+1 415 523 8886).")
                print("   4. Once Twilio replies 'You are all set!', re-run your notification command.")
                print("   (Tip: You can preview the message anytime using: bin/cloudpulse notify --channel whatsapp --dry-run)")
            return False


# Global singleton
finops_notifier = FinOpsNotifier()

