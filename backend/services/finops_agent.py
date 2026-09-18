import json
import os
import requests
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

try:
    from groq import Groq
except ImportError:
    Groq = None

try:
    from mistralai.client import Mistral
except ImportError:
    try:
        from mistralai import Mistral
    except ImportError:
        Mistral = None

from services.cost_analytics import (
    evaluate_inventory_optimizations,
    calculate_finops_health_score,
    calculate_spend_forecast,
    detect_cost_anomalies
)
from services.pricing_service import AWSPricingClient
from services.remediator import AutoRemediator

class FinOpsAgent:
    """
    Autonomous FinOps AI Agent:
    - Multi-tier LLM router (Local Ollama -> Groq Llama-3.1 -> Mistral AI fallback)
    - FinOps slash command engine (/audit, /optimize, /forecast, /health, /pricing, /remediate)
    - AWS Well-Architected & FinOps Foundation grounded diagnostic intelligence
    """

    FINOPS_SYSTEM_PROMPT = """You are the Sovereign FinOps Autonomous AI Agent, specializing in cloud cost optimization, telemetry analytics, and infrastructure security for AWS, GCP, and Azure.
Your knowledge is strictly grounded in the AWS Well-Architected Framework (Cost Optimization and Security Pillars) and FinOps Foundation principles.
When analyzing infrastructure:
1. Always quantify potential monthly savings in USD ($).
2. Distinguish between quick wins (unattached EIPs, orphaned volumes) and architectural rightsizing.
3. Flag critical security exposures (such as 0.0.0.0/0 on port 22/3389) as immediate priorities.
4. Be precise, actionable, and executive-ready."""

    def __init__(self, data_store: Optional[Dict[str, Any]] = None):
        self.data_store = data_store
        self.pricing_client = AWSPricingClient()

        # Local Sovereign Ollama
        self.ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434/api")
        self.local_model = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

        # Cloud Fallback 1: Groq
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.groq_client = Groq(api_key=self.groq_key) if (self.groq_key and Groq) else None

        # Cloud Fallback 2: Mistral AI
        self.mistral_key = os.getenv("MISTRAL_API_KEY")
        self.mistral_client = Mistral(api_key=self.mistral_key) if (self.mistral_key and Mistral) else None

    def _get_current_inventory(self) -> Dict[str, Any]:
        if self.data_store:
            return self.data_store
        from mock_database import DB
        return DB

    def handle_slash_command(self, query: str) -> Optional[Dict[str, Any]]:
        """Parses and executes slash commands."""
        parts = query.strip().split()
        if not parts or not parts[0].startswith("/"):
            return None

        cmd = parts[0].lower()
        args = parts[1:]
        inv = self._get_current_inventory()

        if cmd == "/audit":
            health = calculate_finops_health_score(inv)
            opts = evaluate_inventory_optimizations(inv)
            spend = inv.get("spend", [])
            anomalies = detect_cost_anomalies(spend) if spend else []
            total_savings = sum(o["monthly_savings"] for o in opts)
            return {
                "command": "/audit",
                "type": "audit_report",
                "health_score": health["overall_health_score"],
                "grade": health["grade"],
                "total_savings_potential": round(total_savings, 2),
                "findings_count": len(opts),
                "anomalies_count": len(anomalies),
                "recommendations": opts,
                "anomalies": anomalies,
                "summary": f"FinOps Health Score: {health['overall_health_score']}/100 (Grade {health['grade']}). Discovered {len(opts)} optimizations with ${total_savings:.2f}/mo potential savings."
            }

        elif cmd == "/optimize":
            opts = evaluate_inventory_optimizations(inv)
            total_savings = sum(o["monthly_savings"] for o in opts)
            quick_wins = [o for o in opts if o.get("effort") == "Quick Win"]
            return {
                "command": "/optimize",
                "type": "optimization_plan",
                "total_potential_savings": round(total_savings, 2),
                "quick_wins": quick_wins,
                "all_recommendations": opts,
                "summary": f"Identified {len(opts)} optimization actions totaling ${total_savings:.2f}/month in savings. {len(quick_wins)} quick wins can be executed immediately."
            }

        elif cmd == "/forecast":
            spend = inv.get("spend", [])
            forecast = calculate_spend_forecast(spend, monthly_budget=600.0)
            return {
                "command": "/forecast",
                "type": "cost_forecast",
                "data": forecast,
                "summary": f"Current daily burn is ${forecast['current_daily_burn']:.2f}/day. Projected month-end spend: ${forecast['projected_month_end']:.2f} (Status: {forecast['budget_status'].upper()})."
            }

        elif cmd == "/health":
            health = calculate_finops_health_score(inv)
            return {
                "command": "/health",
                "type": "health_breakdown",
                "data": health,
                "summary": f"FinOps Health Score: {health['overall_health_score']}/100 (Grade: {health['grade']}). Compute: {health['pillars']['compute_efficiency']['score']}/25, Storage: {health['pillars']['storage_optimization']['score']}/25, Network: {health['pillars']['network_cleanliness']['score']}/25, Security: {health['pillars']['security_posture']['score']}/25."
            }

        elif cmd == "/pricing":
            instance_type = args[0] if len(args) > 0 else "t3.medium"
            region = args[1] if len(args) > 1 else "us-east-1"
            monthly = self.pricing_client.get_instance_monthly_cost(instance_type, region)
            hourly = round(monthly / 730.0, 4)
            return {
                "command": "/pricing",
                "type": "pricing_lookup",
                "instance_type": instance_type,
                "region": region,
                "hourly_rate": hourly,
                "monthly_rate": monthly,
                "summary": f"AWS On-Demand pricing for {instance_type} in {region}: ~${hourly}/hr (~${monthly:.2f}/month)."
            }

        elif cmd == "/remediate":
            resource_id = args[0] if args else "dry-run-all"
            remediator = AutoRemediator(dry_run=True)
            opts = evaluate_inventory_optimizations(inv)
            results = []
            for opt in opts:
                if resource_id in ("dry-run-all", opt.get("resource_id"), opt.get("id")):
                    action = opt.get("action")
                    res_id = opt.get("resource_id")
                    if action == "release_eip":
                        res = remediator.release_unattached_eip(res_id)
                    elif action == "delete_volume":
                        res = remediator.delete_unattached_volume(res_id)
                    elif action == "upgrade_gp3":
                        res = remediator.upgrade_volume_to_gp3(res_id)
                    elif action == "stop_instance":
                        res = remediator.stop_idle_instance(res_id)
                    elif action == "set_log_retention":
                        res = remediator.set_log_group_retention(res_id)
                    else:
                        res = {"status": "skipped", "message": f"Action {action} requires manual approval."}
                    results.append(res)

            return {
                "command": "/remediate",
                "type": "remediation_plan",
                "dry_run": True,
                "actions_evaluated": len(results),
                "details": results,
                "summary": f"Evaluated {len(results)} remediation actions in DRY-RUN mode. No changes were applied."
            }

        elif cmd in ("/help", "/?"):
            return {
                "command": "/help",
                "type": "help",
                "commands": [
                    {"command": "/audit", "description": "Run full FinOps and security audit"},
                    {"command": "/optimize", "description": "List prioritized cost savings recommendations"},
                    {"command": "/forecast", "description": "Display monthly burn rate and budget runway"},
                    {"command": "/health", "description": "Display 4-pillar FinOps health score (0-100)"},
                    {"command": "/pricing [type] [region]", "description": "Lookup AWS pricing for instance types"},
                    {"command": "/remediate [id]", "description": "Test or simulate safe automated remediation"}
                ]
            }

        return None

    def ask(self, query: str) -> Dict[str, Any]:
        """
        Processes a user question:
        First checks for slash command. If normal natural language question, routes to hybrid LLMs.
        """
        if query.strip().startswith("/"):
            res = self.handle_slash_command(query)
            if res:
                return res

        # Build context from current infrastructure state
        inv = self._get_current_inventory()
        health = calculate_finops_health_score(inv)
        opts = evaluate_inventory_optimizations(inv)
        total_savings = sum(o["monthly_savings"] for o in opts)

        context = f"""Current Cloud Infrastructure State:
- Health Score: {health['overall_health_score']}/100 (Grade: {health['grade']})
- Total Running Compute Nodes: {len(inv.get('nodes', []))}
- Discovered Optimizations: {len(opts)} actions with ${total_savings:.2f}/mo potential savings
- Top Savings Items:
{chr(10).join([f"  * {o['title']} (Save ${o['monthly_savings']:.2f}/mo)" for o in opts[:3]])}
"""

        # 1. Try Local Ollama first
        try:
            resp = requests.post(
                f"{self.ollama_url}/generate",
                json={
                    "model": self.local_model,
                    "prompt": f"{self.FINOPS_SYSTEM_PROMPT}\n\nContext:\n{context}\n\nUser Question: {query}\n\nFinOps Recommendation:",
                    "stream": False
                },
                timeout=3
            )
            if resp.status_code == 200:
                answer = resp.json().get("response", "").strip()
                if answer:
                    return {"type": "ai_response", "source": "ollama_local", "response": answer}
        except Exception:
            pass

        # 2. Try Groq (Llama 3.1)
        if self.groq_client:
            try:
                chat_completion = self.groq_client.chat.completions.create(
                    messages=[
                        {"role": "system", "content": self.FINOPS_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                    ],
                    model="llama-3.1-8b-instant",
                    temperature=0.3,
                    max_tokens=500
                )
                answer = chat_completion.choices[0].message.content
                return {"type": "ai_response", "source": "groq_cloud", "response": answer}
            except Exception:
                pass

        # 3. Try Mistral AI
        if self.mistral_client:
            try:
                chat_resp = self.mistral_client.chat.complete(
                    model="mistral-small-latest",
                    messages=[
                        {"role": "system", "content": self.FINOPS_SYSTEM_PROMPT},
                        {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {query}"}
                    ]
                )
                answer = chat_resp.choices[0].message.content
                return {"type": "ai_response", "source": "mistral_cloud", "response": answer}
            except Exception:
                pass

        # 4. Sovereign Rule-Based Fallback
        fallback_reply = (
            f"Based on current cloud infrastructure analysis:\n"
            f"• FinOps Health Score: {health['overall_health_score']}/100 (Grade {health['grade']})\n"
            f"• Potential Monthly Savings: ${total_savings:.2f}/month across {len(opts)} recommendations.\n"
            f"• Key Recommendation: {opts[0]['title'] if opts else 'Infrastructure is optimal.'}\n\n"
            f"Tip: Use slash commands like `/audit`, `/optimize`, `/forecast`, or `/health` for in-depth insights."
        )
        return {"type": "ai_response", "source": "rule_based_fallback", "response": fallback_reply}
