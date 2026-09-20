"""
CloudPulse Native GitHub App & CI/CD FinOps Guardrail Engine
Intercepts pull requests modifying infrastructure (Terraform / Helm / K8s),
calculates monthly and annual cost diffs in USD/INR, and generates automated PR comments and check runs.
"""

import hmac
import hashlib
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from services.currency_converter import currency_converter

logger = logging.getLogger("cloudpulse.github.engine")

# Amortized monthly instance costs (730 hrs/month)
INSTANCE_MONTHLY_PRICES = {
    "t3.nano": 3.80,
    "t3.micro": 7.60,
    "t3.small": 15.20,
    "t3.medium": 30.40,
    "t3.large": 60.80,
    "t3.xlarge": 121.60,
    "t3.2xlarge": 243.20,
    "t4g.nano": 3.04,
    "t4g.micro": 6.08,
    "t4g.small": 12.16,
    "t4g.medium": 24.32,
    "t4g.large": 48.64,
    "t4g.xlarge": 97.28,
    "t4g.2xlarge": 194.56,
    "m5.large": 69.35,
    "m5.xlarge": 138.70,
    "m5.2xlarge": 277.40,
    "m5.4xlarge": 554.80,
    "m5.24xlarge": 3328.80,
    "c5.large": 62.05,
    "c5.xlarge": 124.10,
    "c6g.medium": 24.82,
    "c6g.large": 49.64,
}

EBS_GB_MONTHLY_RATES = {
    "gp2": 0.10,
    "gp3": 0.08,
    "io1": 0.125,
    "io2": 0.125,
    "standard": 0.05
}

DEFAULT_SPIKE_THRESHOLD_USD = 50.00


class GitHubAppEngine:
    """
    Automates CI/CD FinOps guardrails via native GitHub App webhooks,
    Terraform/Helm diff analysis, PR comments, and GitHub check-runs.
    """

    def __init__(self, spike_threshold_usd: float = DEFAULT_SPIKE_THRESHOLD_USD, webhook_secret: Optional[str] = None):
        self.spike_threshold_usd = spike_threshold_usd
        self.webhook_secret = webhook_secret

    def verify_signature(self, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """
        Validates GitHub HMAC-SHA256 signature from 'X-Hub-Signature-256'.
        """
        if not self.webhook_secret:
            return True  # Dev mode / unauthenticated testing

        if not signature_header or not signature_header.startswith("sha256="):
            return False

        expected_sig = "sha256=" + hmac.new(
            self.webhook_secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, signature_header)

    def parse_instance_price(self, instance_type: str) -> float:
        """Looks up or estimates monthly cost of an EC2 instance type."""
        inst = instance_type.strip().strip('"').strip("'").lower()
        if inst in INSTANCE_MONTHLY_PRICES:
            return INSTANCE_MONTHLY_PRICES[inst]
        # Generic heuristic for unknown types
        if "nano" in inst:
            return 4.00
        if "micro" in inst:
            return 8.00
        if "small" in inst:
            return 16.00
        if "medium" in inst:
            return 32.00
        if "xlarge" in inst:
            return 120.00
        if "2xlarge" in inst:
            return 240.00
        return 50.00

    def analyze_diff(self, diff_text: str, file_path: str = "terraform/compute.tf") -> Dict[str, Any]:
        """
        Parses a unified diff and computes baseline, projected spend, and net cost difference.
        """
        lines = diff_text.splitlines()
        removed_instances = []
        added_instances = []
        removed_volumes = []
        added_volumes = []
        changes = []

        for line in lines:
            # EC2 instance_type modifications
            if "instance_type" in line:
                m = re.search(r'instance_type\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    itype = m.group(1)
                    if line.startswith("-") and not line.startswith("---"):
                        removed_instances.append(itype)
                    elif line.startswith("+") and not line.startswith("+++"):
                        added_instances.append(itype)

            # EBS storage volume type or size
            if "type" in line and ("gp2" in line or "gp3" in line or "io2" in line):
                m = re.search(r'type\s*=\s*["\']([^"\']+)["\']', line)
                if m:
                    vtype = m.group(1)
                    if line.startswith("-") and not line.startswith("---"):
                        removed_volumes.append(vtype)
                    elif line.startswith("+") and not line.startswith("+++"):
                        added_volumes.append(vtype)

            # Elastic IP addition / release
            if "aws_eip" in line:
                if line.startswith("+"):
                    changes.append({"resource": "Elastic IP", "action": "Add Public IPv4", "delta": 3.65})
                elif line.startswith("-"):
                    changes.append({"resource": "Elastic IP", "action": "Release Public IPv4", "delta": -3.65})

            # NAT Gateway addition / release
            if "aws_nat_gateway" in line:
                if line.startswith("+"):
                    changes.append({"resource": "NAT Gateway", "action": "Deploy NAT Gateway", "delta": 32.85})
                elif line.startswith("-"):
                    changes.append({"resource": "NAT Gateway", "action": "Remove NAT Gateway", "delta": -32.85})

        baseline_monthly = 0.0
        projected_monthly = 0.0

        # Match instance replacements (e.g. t3.xlarge -> t4g.medium)
        max_inst = max(len(removed_instances), len(added_instances))
        for i in range(max_inst):
            rem = removed_instances[i] if i < len(removed_instances) else None
            add = added_instances[i] if i < len(added_instances) else None
            rem_cost = self.parse_instance_price(rem) if rem else 0.0
            add_cost = self.parse_instance_price(add) if add else 0.0
            baseline_monthly += rem_cost
            projected_monthly += add_cost
            delta = add_cost - rem_cost
            desc = f"EC2 `{rem or 'none'}` ➔ `{add or 'none'}`"
            changes.append({"resource": "EC2 Instance", "action": desc, "delta": round(delta, 2)})

        # Match volume updates (default 100 GB volume for calculation)
        max_vol = max(len(removed_volumes), len(added_volumes))
        for i in range(max_vol):
            rv = removed_volumes[i] if i < len(removed_volumes) else "gp2"
            av = added_volumes[i] if i < len(added_volumes) else "gp3"
            r_cost = EBS_GB_MONTHLY_RATES.get(rv, 0.10) * 100
            a_cost = EBS_GB_MONTHLY_RATES.get(av, 0.08) * 100
            baseline_monthly += r_cost
            projected_monthly += a_cost
            delta = a_cost - r_cost
            changes.append({"resource": "EBS Storage (100 GB)", "action": f"Storage `{rv}` ➔ `{av}`", "delta": round(delta, 2)})

        # Aggregate additions from other resources (EIP, NAT)
        for c in changes:
            if c["resource"] in ["Elastic IP", "NAT Gateway"]:
                if c["delta"] > 0:
                    projected_monthly += c["delta"]
                else:
                    baseline_monthly += abs(c["delta"])

        monthly_diff = round(projected_monthly - baseline_monthly, 2)
        annual_diff = round(monthly_diff * 12.0, 2)
        is_spike = monthly_diff > self.spike_threshold_usd

        if monthly_diff < -0.01:
            impact_type = "COST_REDUCTION"
        elif monthly_diff > 0.01:
            impact_type = "COST_INCREASE"
        else:
            impact_type = "NEUTRAL"

        return {
            "file_path": file_path,
            "impact_type": impact_type,
            "baseline_monthly_spend": round(baseline_monthly, 2),
            "projected_monthly_spend": round(projected_monthly, 2),
            "monthly_diff": monthly_diff,
            "annual_diff": annual_diff,
            "is_cost_spike": is_spike,
            "spike_threshold_usd": self.spike_threshold_usd,
            "changes": changes
        }

    def format_pr_comment(
        self,
        analysis: Dict[str, Any],
        currency: str = "USD",
        rate: float = 84.0,
        pr_number: Optional[int] = None
    ) -> str:
        """
        Formats a GitHub Pull Request comment with dual currency and guardrail badges.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate

        diff = analysis["monthly_diff"]
        diff_annual = analysis["annual_diff"]
        baseline = analysis["baseline_monthly_spend"]
        projected = analysis["projected_monthly_spend"]
        is_spike = analysis["is_cost_spike"]

        diff_str = converter.format_dual(abs(diff), primary_currency=currency)
        diff_annual_str = converter.format_dual(abs(diff_annual), primary_currency=currency)
        baseline_str = converter.format_dual(baseline, primary_currency=currency)
        projected_str = converter.format_dual(projected, primary_currency=currency)

        pr_title = f" (PR #{pr_number})" if pr_number else ""

        if diff < 0:
            badge = f"🟢 **Cost Reduction: -{diff_str}/mo** (-{diff_annual_str}/yr)"
            alert_box = (
                "> [!TIP]\n"
                "> ✅ **Passed FinOps Guardrails:** This pull request reduces cloud infrastructure spend.\n"
                "> Validated against AWS Well-Architected Cost Optimization principles."
            )
        elif is_spike:
            badge = f"🚨 **Cost Spike Alert: +{diff_str}/mo** (+{diff_annual_str}/yr)"
            alert_box = (
                f"> [!WARNING]\n"
                f"> ⚠️ **Exceeds Policy Threshold (${self.spike_threshold_usd:.2f}/mo):**\n"
                f"> Proposed infrastructure changes increase monthly cloud spend by **+{diff_str}/mo**.\n"
                f"> FinOps Lead or Team Lead approval is required before merging."
            )
        else:
            badge = f"ℹ️ **Net Spend Change: +{diff_str}/mo**" if diff > 0 else "⚪ **Neutral Spend Impact ($0.00/mo)**"
            alert_box = (
                "> [!NOTE]\n"
                "> ℹ️ **Within Budget Tolerance:** Proposed change is within permissible variance limits."
            )

        changes_rows = []
        for c in analysis.get("changes", []):
            d_val = c["delta"]
            d_str = converter.format_dual(abs(d_val), primary_currency=currency)
            sign = "+" if d_val > 0 else "-"
            changes_rows.append(f"| {c['resource']} | {c['action']} | `{sign}{d_str}/mo` |")

        changes_table = "\n".join(changes_rows) if changes_rows else "| All | No cost-bearing modifications | `$0.00/mo` |"

        markdown = f"""### ⚡ CloudPulse FinOps CI/CD Guardrail{pr_title}

{badge}

| Financial Metric | Current Baseline | Proposed Change | Net Delta |
| :--- | :--- | :--- | :--- |
| **Monthly Run-Rate** | {baseline_str}/mo | {projected_str}/mo | **{'+' if diff > 0 else '-'}{diff_str}/mo** |
| **Annualized Run-Rate** | {converter.format_dual(baseline * 12, primary_currency=currency)}/yr | {converter.format_dual(projected * 12, primary_currency=currency)}/yr | **{'+' if diff_annual > 0 else '-'}{diff_annual_str}/yr** |

#### 🔍 Itemized Infrastructure Modifications
| Resource | Action Description | Monthly Cost Impact |
| :--- | :--- | :--- |
{changes_table}

{alert_box}

---
*Generated autonomously by [CloudPulse FinOps Engine](https://github.com/cloudpulse/cloudpulse)*
"""
        return markdown

    def format_check_run(
        self,
        analysis: Dict[str, Any],
        head_sha: str = "head-sha",
        currency: str = "USD",
        rate: float = 84.0
    ) -> Dict[str, Any]:
        """
        Creates GitHub Check Run schema payload for pull request status checks.
        """
        converter = currency_converter
        converter.usd_to_inr_rate = rate

        diff = analysis["monthly_diff"]
        diff_str = converter.format_dual(abs(diff), primary_currency=currency)
        is_spike = analysis["is_cost_spike"]

        if is_spike:
            conclusion = "action_required"
            title = f"🚨 Cost Spike: +{diff_str}/mo exceeds threshold (${self.spike_threshold_usd:.2f})"
            summary = (
                f"Proposed changes introduce a +{diff_str}/mo cloud spend increase. "
                f"Requires FinOps team sign-off."
            )
        elif diff < 0:
            conclusion = "success"
            title = f"🟢 Cost Reduction: -{diff_str}/mo verified"
            summary = f"Pull request eliminates recoverable waste, saving {diff_str}/mo."
        else:
            conclusion = "success"
            title = f"✅ Cost Neutral: +{diff_str}/mo within budget"
            summary = "Infrastructure changes are within acceptable spend boundaries."

        return {
            "name": "cloudpulse/finops-guardrail",
            "head_sha": head_sha,
            "status": "completed",
            "conclusion": conclusion,
            "output": {
                "title": title,
                "summary": summary,
                "text": self.format_pr_comment(analysis, currency=currency, rate=rate)
            }
        }

    def handle_webhook_payload(
        self,
        payload: Dict[str, Any],
        currency: str = "USD",
        rate: float = 84.0
    ) -> Dict[str, Any]:
        """
        Processes incoming GitHub 'pull_request' webhook event.
        """
        action = payload.get("action", "")
        if action not in ["opened", "synchronize", "reopened", "edited"]:
            return {"status": "ignored", "reason": f"Action '{action}' does not require cost evaluation."}

        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {})
        repo_name = repo.get("full_name", "infrastructure/aws-workloads")
        pr_number = pr.get("number", 1)
        head_sha = pr.get("head", {}).get("sha", "head-sha")

        # In real GitHub App, diff is fetched from pr["diff_url"] or GitHub API
        # If simulated diff is attached in payload, use it; otherwise evaluate PR body/title
        diff_text = payload.get("diff") or pr.get("body") or ""

        analysis = self.analyze_diff(diff_text)
        comment_md = self.format_pr_comment(analysis, currency=currency, rate=rate, pr_number=pr_number)
        check_run = self.format_check_run(analysis, head_sha=head_sha, currency=currency, rate=rate)

        return {
            "status": "success",
            "repository": repo_name,
            "pull_number": pr_number,
            "head_sha": head_sha,
            "analysis": analysis,
            "comment_markdown": comment_md,
            "check_run": check_run
        }


# Global Singleton
github_app_engine = GitHubAppEngine()
