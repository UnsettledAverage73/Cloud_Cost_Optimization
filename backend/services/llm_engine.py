import os
import sys
import glob
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("cloudpulse.llm_engine")

def _load_env():
    for p in [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".env"),
    ]:
        if os.path.exists(p):
            try:
                with open(p, "r") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() not in os.environ:
                                os.environ[k.strip()] = v.strip().strip("'\"")
            except Exception:
                pass

def _discover_venv():
    for base in [os.getcwd(), os.path.dirname(os.path.abspath(__file__))]:
        for pattern in [
            os.path.join(base, "venv", "lib", "python*", "site-packages"),
            os.path.join(base, "..", "venv", "lib", "python*", "site-packages"),
            os.path.join(base, "..", "..", "venv", "lib", "python*", "site-packages"),
        ]:
            for sp in glob.glob(pattern):
                if sp not in sys.path:
                    sys.path.insert(0, sp)

_discover_venv()
_load_env()

def _get_groq_key() -> Optional[str]:
    if os.getenv("GROQ_API_KEY"):
        return os.getenv("GROQ_API_KEY")
    cfg_file = os.path.expanduser("~/.config/cloudpulse/config.json")
    if os.path.exists(cfg_file):
        try:
            with open(cfg_file, "r") as f:
                data = json.load(f)
                return data.get("groq_api_key")
        except Exception:
            pass
    return None

PREFERRED_MODELS = [
    "groq/compound-mini",
    "groq/compound",
    "qwen/qwen3.8-27b",
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
]

FINOPS_SYSTEM_PROMPT = """You are CloudPulse FinOps Copilot, an elite autonomous FinOps AI Architect, Principal Cloud Economist, and Site Reliability Engineer.
Your mission is to help engineering, DevOps, and finance teams eliminate cloud waste, understand complex telemetry, investigate spend spikes, and safely remediate infrastructure via Terraform/OpenTofu.

Core Guidelines:
1. Ground all recommendations in the AWS Well-Architected Framework (Cost Optimization, Operational Excellence, and Security Pillars) and FinOps Foundation principles.
2. Always be quantitative, actionable, and executive-ready: cite specific dollar figures ($), percentages (%), and resource IDs where applicable.
3. Categorize actions clearly into Quick Wins (immediate zero-risk actions like unattached EIPs or orphaned EBS volumes) versus Architectural Rightsizing (burstable types, Graviton migration).
4. Emphasize zero-downtime and high-availability best practices when downsizing or modernizing instances.
5. Format output with clean, readable Markdown (bullet points, comparison tables, and code snippets).
"""

class LLMEngine:
    """
    Unified FinOps LLM Engine powered by Groq with multi-model fallback,
    automated retry, and deterministic safety fallback.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or _get_groq_key()
        self.client = None
        self.active_model = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("No Groq API key available. Running in fallback mode.")
            return

        try:
            from groq import Groq
            self.client = Groq(api_key=self.api_key)
            # Find first active model from preferred list
            self.active_model = PREFERRED_MODELS[0]
            logger.info(f"Initialized LLMEngine with Groq (preferred model: {self.active_model})")
        except Exception as e:
            logger.warning(f"Failed to initialize Groq client: {e}")
            self.client = None

    def is_available(self) -> bool:
        return self.client is not None

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.2,
        model: Optional[str] = None
    ) -> Optional[str]:
        """
        Executes chat completion with cascading model fallback.
        """
        if not self.client:
            return None

        models_to_try = [model] if model else PREFERRED_MODELS

        for candidate in models_to_try:
            if not candidate:
                continue
            try:
                response = self.client.chat.completions.create(
                    model=candidate,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature
                )
                if response.choices and response.choices[0].message.content:
                    self.active_model = candidate
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.debug(f"Model {candidate} failed: {e}. Trying next fallback...")
                continue

        logger.warning("All LLM models in cascade failed.")
        return None

    def ask_finops(self, query: str, context: Optional[str] = None, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Processes general FinOps queries with rich cloud context.
        """
        sys_prompt = system_prompt or FINOPS_SYSTEM_PROMPT
        user_content = f"Context:\n{context}\n\nQuestion: {query}" if context else query

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        reply = self.chat_completion(messages, max_tokens=1200, temperature=0.2)
        if reply:
            return {
                "response": reply,
                "provider": "groq",
                "model": self.active_model,
                "status": "success"
            }

        return {
            "response": "Autonomous FinOps analysis based on deterministic heuristics. Provide valid cloud credentials or ask a specific slash command (/audit, /optimize, /forecast, /health).",
            "provider": "rule_fallback",
            "model": "deterministic",
            "status": "fallback"
        }

    def explain_anomaly(self, anomaly: Dict[str, Any], context: Optional[str] = None) -> Dict[str, Any]:
        """
        Generates root-cause forensics and step-by-step mitigation plan for spend spikes.
        """
        prompt = (
            f"Anomalous cost surge detected:\n"
            f"- Date: {anomaly.get('day', 'Recent')}\n"
            f"- Spiked Spend: ${anomaly.get('cost', 0):.2f}\n"
            f"- Baseline Expected Mean: ${anomaly.get('expected_mean', 0):.2f}\n"
            f"- Spike Percentage: +{anomaly.get('spike_percentage', 0)}%\n"
            f"- Severity: {anomaly.get('severity', 'HIGH')}\n"
        )
        if context:
            prompt += f"\nInfrastructure Telemetry Context:\n{context}\n"

        prompt += "\nProvide a concise 3-part FinOps analysis:\n1. Root-cause hypothesis\n2. Financial blast-radius\n3. Immediate containment and remediation actions."

        messages = [
            {"role": "system", "content": FINOPS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        explanation = self.chat_completion(messages, max_tokens=800, temperature=0.1)
        if explanation:
            return {
                "explanation": explanation,
                "provider": "groq",
                "model": self.active_model
            }

        # Deterministic fallback
        return {
            "explanation": (
                f"Spend on {anomaly.get('day')} reached ${anomaly.get('cost', 0):.2f}, "
                f"exceeding the 7-day rolling baseline of ${anomaly.get('expected_mean', 0):.2f} by "
                f"+{anomaly.get('spike_percentage', 0)}%. Review newly provisioned EC2/EBS resources in us-east-1."
            ),
            "provider": "rule_fallback",
            "model": "deterministic"
        }

    def generate_terraform_pr(
        self,
        finding_id: str,
        resource_id: str,
        action_type: str,
        current_config: Dict[str, Any],
        recommended_config: Dict[str, Any],
        monthly_savings: float
    ) -> Dict[str, Any]:
        """
        Uses Groq to generate production-ready Terraform / OpenTofu HCL code and PR body.
        """
        prompt = (
            f"Generate an enterprise Terraform / OpenTofu Pull Request to remediate this finding:\n"
            f"- Finding ID: {finding_id}\n"
            f"- Target Resource ID: {resource_id}\n"
            f"- Action Type: {action_type}\n"
            f"- Current Config: {json.dumps(current_config)}\n"
            f"- Recommended Config: {json.dumps(recommended_config)}\n"
            f"- Estimated Monthly Savings: ${monthly_savings:.2f}/month\n\n"
            f"Return clean JSON with these exact keys:\n"
            f'{{"hcl_diff": "<unified diff code>", "pr_title": "<concise commit/PR title>", "pr_description": "<markdown PR body with impact, safety checks, and rollback>", "validation_command": "terraform plan -target=aws_instance.<name>"}}'
        )

        messages = [
            {"role": "system", "content": "You are a Cloud Infrastructure Architect. Respond ONLY in valid JSON matching the requested keys."},
            {"role": "user", "content": prompt}
        ]

        raw_response = self.chat_completion(messages, max_tokens=1000, temperature=0.1)
        if raw_response:
            try:
                # Strip markdown code fences if LLM wrapped in ```json ... ```
                clean = raw_response.strip()
                if clean.startswith("```json"):
                    clean = clean[7:]
                elif clean.startswith("```"):
                    clean = clean[3:]
                if clean.endswith("```"):
                    clean = clean[:-3]
                parsed = json.loads(clean.strip())
                parsed["provider"] = "groq"
                parsed["model"] = self.active_model
                return parsed
            except Exception as e:
                logger.warning(f"Failed to parse LLM Terraform JSON: {e}")

        # High-fidelity fallback
        res_name = current_config.get("name", resource_id.replace("-", "_"))
        curr_t = current_config.get("instance_type", "m5.2xlarge")
        rec_t = recommended_config.get("instance_type", "t4g.medium")
        diff = (
            f"--- a/terraform/compute.tf\n"
            f"+++ b/terraform/compute.tf\n"
            f"@@ -10,4 +10,5 @@ resource \"aws_instance\" \"{res_name}\" {{\n"
            f"-  instance_type = \"{curr_t}\"\n"
            f"+  instance_type = \"{rec_t}\"\n"
            f"+  # CloudPulse FinOps: Saves ${monthly_savings:.2f}/mo"
        )
        return {
            "hcl_diff": diff,
            "pr_title": f"feat(finops): rightsize {resource_id} to {rec_t} (-${monthly_savings:.2f}/mo)",
            "pr_description": (
                f"## 🚀 CloudPulse Automated FinOps PR\n\n"
                f"- **Target:** `{resource_id}`\n"
                f"- **Monthly Savings:** `${monthly_savings:.2f}/mo`\n"
                f"- **Safety Plan:** Verify CloudWatch CPU P95 < 5% prior to merge."
            ),
            "validation_command": f"terraform plan -target=aws_instance.{res_name}",
            "provider": "rule_fallback",
            "model": "deterministic"
        }

    def generate_recommendation_rationale(self, finding: Dict[str, Any]) -> str:
        """
        Generates executive architectural rationale explaining why an optimization is safe and recommended.
        """
        prompt = (
            f"Write a crisp 2-sentence FinOps engineering rationale for this optimization finding:\n"
            f"- Finding: {finding.get('title')}\n"
            f"- Resource: {finding.get('resource_id')}\n"
            f"- Action: {finding.get('action')}\n"
            f"- Monthly Savings: ${finding.get('monthly_savings', 0):.2f}/mo\n"
            f"- Effort: {finding.get('effort')}\n"
            f"- Details: {finding.get('description')}\n"
        )
        messages = [
            {"role": "system", "content": "You are a Senior Cloud Economist. Be concise, punchy, and specify exact numbers and zero-risk guardrails."},
            {"role": "user", "content": prompt}
        ]
        rationale = self.chat_completion(messages, max_tokens=150, temperature=0.1)
        if rationale:
            return rationale.strip()
        return finding.get("description", "Recommended by CloudPulse FinOps rules.")

    def audit_executive_summary(
        self,
        health_score: float,
        grade: str,
        findings: List[Dict[str, Any]],
        spend: List[Dict[str, Any]]
    ) -> str:
        """
        Generates a C-level FinOps executive briefing based on full infrastructure state.
        """
        total_savings = sum(f.get("monthly_savings", 0.0) for f in findings)
        prompt = (
            f"Generate a 3-paragraph C-level FinOps Executive Briefing:\n"
            f"- Infrastructure Health Score: {health_score}/100 (Grade: {grade})\n"
            f"- Discovered Optimizations: {len(findings)} findings\n"
            f"- Total Recoverable Waste: ${total_savings:.2f}/month (${total_savings * 12:.2f}/year)\n"
            f"- Top 3 Findings:\n" +
            "\n".join([f"  * {f.get('title')} (${f.get('monthly_savings', 0):.2f}/mo)" for f in findings[:3]])
        )
        messages = [
            {"role": "system", "content": FINOPS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        summary = self.chat_completion(messages, max_tokens=400, temperature=0.2)
        if summary:
            return summary.strip()
        return f"FinOps Health Score is {health_score}/100 (Grade {grade}). Identified ${total_savings:.2f}/mo in recoverable cloud waste across {len(findings)} optimization vectors."

# Global singleton
llm_engine = LLMEngine()
