"""
CloudPulse FinOps RAG (Retrieval-Augmented Generation) Engine
Unified RAG architecture powered by Groq LLM for autonomous cloud cost optimization.

Stages:
1. RETRIEVE: Aggregates live cloud telemetry (EC2, EBS, EIP, SGs, CloudWatch, S3),
             AWS real-time pricing rate cards, and historical spend baselines.
2. AUGMENT:  Computes FinOps unit economics (Graviton delta, idle waste, gp2->gp3 savings),
             correlates security exposure, and constructs grounded Well-Architected prompts.
3. GENERATE: Dispatches to high-throughput Groq LLM (groq/compound-mini, groq/compound,
             qwen/qwen3.8-27b) with deterministic fallback for executive recommendations,
             natural language Q&A, and Terraform remediation PRs.
"""

import os
import json
import logging
import re
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone

try:
    from services.llm_engine import llm_engine, FINOPS_SYSTEM_PROMPT
    from copilot.tools.pricing_rag_tool import lookup_aws_pricing, AWS_INSTANCE_PRICING_TABLE, STORAGE_PRICING_TABLE
    from engines.finops_analyzer import FinOpsAnalyzer
    from services.vector_store import vector_knowledge_store
    from services.query_cache import query_cache
except ImportError:
    from backend.services.llm_engine import llm_engine, FINOPS_SYSTEM_PROMPT
    from backend.copilot.tools.pricing_rag_tool import lookup_aws_pricing, AWS_INSTANCE_PRICING_TABLE, STORAGE_PRICING_TABLE
    from backend.engines.finops_analyzer import FinOpsAnalyzer
    from backend.services.vector_store import vector_knowledge_store
    from backend.services.query_cache import query_cache

logger = logging.getLogger("cloudpulse.finops_rag")


class FinOpsRAGPipeline:
    """
    Production-grade FinOps RAG Pipeline:
    - Multi-domain telemetry retrieval (Compute, Storage, Network, Security, Logs)
    - Pricing catalog & Graviton ROI augmentation
    - Groq LLM synthesis for conversational intelligence and executive optimization reports
    """

    def __init__(self, data_store: Optional[Dict[str, Any]] = None):
        self.data_store = data_store
        self.engine = llm_engine

    def _get_inventory(self, inventory: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Resolves the inventory dictionary from argument, data_store, or mock_database."""
        if inventory:
            return inventory
        if self.data_store:
            return self.data_store
        try:
            from mock_database import DB
            return DB
        except ImportError:
            try:
                from backend.mock_database import DB
                return DB
            except Exception:
                return {}

    def _get_inventory_fingerprint(self, inventory: Dict[str, Any]) -> str:
        """Computes a lightweight state fingerprint to validate query cache validity."""
        meta = inventory.get("metadata", {})
        ts = meta.get("timestamp", "")
        spend = inventory.get("summary", {}).get("estimated_monthly_spend", 0.0)
        nodes = inventory.get("compute", {}).get("nodes") or inventory.get("nodes", [])
        ec2_other = inventory.get("ec2_other_resources", {})
        vols = ec2_other.get("ebs_volumes") or inventory.get("ebs_volumes", [])
        return f"{ts}:{spend}:{len(nodes)}:{len(vols)}"

    # =========================================================================
    # 1. RETRIEVE STAGE
    # =========================================================================
    def retrieve_context(
        self,
        query: Optional[str] = None,
        inventory: Optional[Dict[str, Any]] = None,
        focus_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Retrieves relevant cloud inventory, telemetry, and pricing rate cards based
        on query keywords or focus domain.
        """
        inv = self._get_inventory(inventory)
        query_str = (query or "").lower().strip()

        # Extract standard resources from inventory
        nodes = inv.get("compute", {}).get("nodes") or inv.get("nodes", [])
        ec2_other = inv.get("ec2_other_resources", {})
        ebs_vols = ec2_other.get("ebs_volumes") or inv.get("ebs_volumes", [])
        eips = ec2_other.get("elastic_ips") or inv.get("elastic_ips", [])
        sgs = ec2_other.get("security_groups") or inv.get("security_groups", [])
        cw_logs = ec2_other.get("cloudwatch_log_groups") or inv.get("cloudwatch_log_groups", [])
        vpc_res = inv.get("vpc_resources", {})
        nat_gws = vpc_res.get("nat_gateways", [])
        metadata = inv.get("metadata", {"region": "us-east-1"})

        # Domain classification
        domain_matches = set()
        if focus_domain:
            domain_matches.add(focus_domain.lower())

        if query_str:
            if any(w in query_str for w in ["ec2", "instance", "compute", "cpu", "node", "server", "rightsize", "graviton"]):
                domain_matches.add("compute")
            if any(w in query_str for w in ["ebs", "volume", "disk", "storage", "gp2", "gp3", "snapshot"]):
                domain_matches.add("storage")
            if any(w in query_str for w in ["eip", "ip", "elastic ip", "nat", "network", "bandwidth", "ipv4"]):
                domain_matches.add("network")
            if any(w in query_str for w in ["security", "port", "sg", "firewall", "ingress", "vulnerability", "ssh"]):
                domain_matches.add("security")
            if any(w in query_str for w in ["log", "cloudwatch", "retention", "logging"]):
                domain_matches.add("logs")

        # Default to full infrastructure retrieval if no specific domain matched
        is_broad_query = len(domain_matches) == 0 or "all" in domain_matches

        retrieved_nodes = nodes if (is_broad_query or "compute" in domain_matches) else []
        retrieved_vols = ebs_vols if (is_broad_query or "storage" in domain_matches) else []
        retrieved_eips = eips if (is_broad_query or "network" in domain_matches) else []
        retrieved_sgs = sgs if (is_broad_query or "security" in domain_matches) else []
        retrieved_logs = cw_logs if (is_broad_query or "logs" in domain_matches) else []

        # Check for specific resource ID mentions in query (e.g. i-036358db85d245e3a or vol-0992817361abce)
        if query_str:
            for n in nodes:
                if n.get("instance_id", "").lower() in query_str and n not in retrieved_nodes:
                    retrieved_nodes.append(n)
            for v in ebs_vols:
                if v.get("volume_id", "").lower() in query_str and v not in retrieved_vols:
                    retrieved_vols.append(v)
            for s in sgs:
                if s.get("group_id", "").lower() in query_str and s not in retrieved_sgs:
                    retrieved_sgs.append(s)

        # Retrieve relevant AWS pricing rate cards
        pricing_rate_cards = {}
        for n in retrieved_nodes:
            itype = n.get("instance_type") or n.get("type", "t3.micro")
            if itype not in pricing_rate_cards:
                pricing_rate_cards[itype] = lookup_aws_pricing(itype)

        # Check for fleet-wide information
        fleet_summary = None
        try:
            from collectors.fleet_cache import fleet_cache
            fleet_summary = fleet_cache.get("fleet_summary")
        except Exception:
            try:
                from backend.collectors.fleet_cache import fleet_cache
                fleet_summary = fleet_cache.get("fleet_summary")
            except Exception:
                pass

        # Hybrid Semantic Vector Search across FinOps policies
        semantic_policies = []
        if query_str:
            try:
                semantic_policies = vector_knowledge_store.search(query=query_str, top_k=2)
            except Exception as e:
                logger.debug(f"Vector search exception: {e}")

        # Anomaly and Forecasting Signals
        anomalies = []
        forecast = None
        if query_str and any(w in query_str for w in ["anomal", "spike", "surge", "idle", "waste"]):
            try:
                try:
                    from services.anomaly_detector import anomaly_detector
                except ImportError:
                    from backend.services.anomaly_detector import anomaly_detector
                anomalies = anomaly_detector.get_anomalies()
            except Exception:
                pass

        if query_str and any(w in query_str for w in ["forecast", "budget", "burn", "trend", "project", "run rate", "run-rate"]):
            try:
                try:
                    from services.spend_forecaster import spend_forecaster
                except ImportError:
                    from backend.services.spend_forecaster import spend_forecaster
                forecast = spend_forecaster.forecast_from_inventory(inv, forecast_days=30)
            except Exception:
                pass

        return {
            "metadata": metadata,
            "domains": list(domain_matches) if domain_matches else ["all"],
            "is_broad": is_broad_query,
            "nodes": retrieved_nodes,
            "ebs_volumes": retrieved_vols,
            "elastic_ips": retrieved_eips,
            "security_groups": retrieved_sgs,
            "cloudwatch_logs": retrieved_logs,
            "nat_gateways": nat_gws,
            "pricing_rate_cards": pricing_rate_cards,
            "fleet_summary": fleet_summary,
            "semantic_policies": semantic_policies,
            "anomalies": anomalies,
            "forecast": forecast,
            "total_retrieved_items": (
                len(retrieved_nodes) + len(retrieved_vols) + len(retrieved_eips) +
                len(retrieved_sgs) + len(retrieved_logs)
            )
        }

    # =========================================================================
    # 2. AUGMENT STAGE
    # =========================================================================
    def augment_context(self, retrieved: Dict[str, Any], user_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Augments the retrieved raw entities with FinOps unit economics, calculated savings,
        security risk assessments, and Well-Architected Framework guidelines.
        """
        nodes = retrieved.get("nodes", [])
        vols = retrieved.get("ebs_volumes", [])
        eips = retrieved.get("elastic_ips", [])
        sgs = retrieved.get("security_groups", [])
        logs = retrieved.get("cloudwatch_logs", [])
        pricing_cards = retrieved.get("pricing_rate_cards", {})

        augmented_compute = []
        total_compute_savings = 0.0
        for n in nodes:
            iid = n.get("instance_id")
            itype = n.get("instance_type") or n.get("type", "t3.micro")
            state = n.get("state", "running")
            metrics = n.get("metrics", {})
            cpu_avg = metrics.get("cpu_utilization_avg", 0.0)
            cost = float(n.get("cost", 7.60))
            is_idle = cpu_avg < 5.0 and state == "running"

            # Compute Graviton savings
            rate_info = pricing_cards.get(itype, {})
            graviton = rate_info.get("graviton_recommendation")
            graviton_savings = graviton.get("monthly_savings", 0.0) if graviton else 0.0

            suggested_downsize = None
            if is_idle:
                # Idle downsize to nano or stop
                suggested_savings = round(cost * 0.70, 2)
                suggested_downsize = f"Downsize/Stop idle compute (Save ${suggested_savings:.2f}/mo)"
                total_compute_savings += suggested_savings
            elif graviton:
                suggested_downsize = f"Migrate to Graviton {graviton.get('instance_type')} (Save ${graviton_savings:.2f}/mo)"
                total_compute_savings += graviton_savings

            augmented_compute.append({
                "instance_id": iid,
                "name": n.get("name", "unnamed"),
                "type": itype,
                "state": state,
                "cpu_avg": cpu_avg,
                "cost_monthly": cost,
                "is_idle": is_idle,
                "graviton_recommendation": graviton,
                "suggested_action": suggested_downsize
            })

        # Augment EBS Storage
        augmented_storage = []
        total_storage_savings = 0.0
        for v in vols:
            vid = v.get("volume_id")
            vtype = v.get("volume_type", "gp2")
            size_gb = float(v.get("size_gb", 10.0))
            cost = float(v.get("cost", 1.00))
            is_orphaned = v.get("is_orphaned") or v.get("status") == "available"

            action = None
            savings = 0.0
            if is_orphaned:
                savings = cost
                action = f"Delete orphaned volume (Save ${savings:.2f}/mo, 100% waste)"
                total_storage_savings += savings
            elif vtype == "gp2":
                savings = round(size_gb * 0.02, 2)
                action = f"Upgrade gp2 -> gp3 (Save ${savings:.2f}/mo, 20% discount + 3000 baseline IOPS)"
                total_storage_savings += savings

            augmented_storage.append({
                "volume_id": vid,
                "type": vtype,
                "size_gb": size_gb,
                "cost_monthly": cost,
                "is_orphaned": is_orphaned,
                "action": action,
                "savings": savings
            })

        # Augment Network & EIPs
        augmented_network = []
        total_network_savings = 0.0
        for e in eips:
            pip = e.get("public_ip")
            is_unattached = e.get("is_unattached") or not e.get("association_id")
            savings = 3.60 if is_unattached else 0.0
            if is_unattached:
                total_network_savings += savings

            augmented_network.append({
                "public_ip": pip,
                "is_unattached": is_unattached,
                "hourly_rate": "$0.005/hr (AWS idle IPv4 surcharge)",
                "savings": savings,
                "action": "Release unattached Elastic IP" if is_unattached else "In use"
            })

        # Augment Security Groups
        augmented_security = []
        for s in sgs:
            gid = s.get("group_id")
            gname = s.get("group_name", "default")
            is_exposed = s.get("is_publicly_exposed", False)
            exposed_ports = s.get("exposed_ports", [])
            inbound = s.get("inbound_rules", [])

            # Check if port 22 or 3389 is exposed to world
            high_risk_ports = []
            for r in inbound:
                if r.get("is_open_to_world"):
                    fp = r.get("from_port")
                    if fp in [22, 3389, 80, 443]:
                        high_risk_ports.append(fp)

            augmented_security.append({
                "group_id": gid,
                "group_name": gname,
                "is_publicly_exposed": is_exposed or len(high_risk_ports) > 0,
                "high_risk_ports": high_risk_ports or exposed_ports,
                "recommendation": "Restrict CIDR to corporate VPN/bastion" if (is_exposed or high_risk_ports) else "Secure"
            })

        # Augment CloudWatch Logs
        augmented_logs = []
        total_logs_savings = 0.0
        for lg in logs:
            name = lg.get("log_group_name")
            retention = lg.get("retention_in_days")
            is_never_expire = lg.get("is_never_expire") or (retention is None)
            stored_gb = float(lg.get("stored_gb", 0.0))
            cost = float(lg.get("cost", 0.0))
            savings = round(cost * 0.50, 2) if is_never_expire else 0.0
            if is_never_expire:
                total_logs_savings += savings

            augmented_logs.append({
                "log_group_name": name,
                "retention_days": retention or "Never Expire",
                "is_never_expire": is_never_expire,
                "stored_gb": stored_gb,
                "monthly_cost": cost,
                "action": "Enforce 30-day retention policy" if is_never_expire else "Compliant",
                "savings": savings
            })

        total_recoverable_monthly = round(
            total_compute_savings + total_storage_savings + total_network_savings + total_logs_savings, 2
        )
        total_recoverable_annual = round(total_recoverable_monthly * 12.0, 2)

        # Build clean Markdown knowledge chunk for LLM ingestion
        knowledge_chunks = []
        knowledge_chunks.append("### 🌐 LIVE RETRIEVED TELEMETRY & FINOPS BENCHMARKS:")

        if augmented_compute:
            knowledge_chunks.append("\n**Compute Instances (EC2):**")
            for c in augmented_compute:
                idle_tag = "⚠️ IDLE" if c["is_idle"] else "Active"
                grav_tag = f" -> Graviton recommendation: {c['graviton_recommendation']['instance_type']} (Save ${c['graviton_recommendation']['monthly_savings']}/mo)" if c['graviton_recommendation'] else ""
                knowledge_chunks.append(
                    f"- `{c['instance_id']}` ({c['name']}): {c['type']}, State: {c['state']}, Avg CPU: {c['cpu_avg']}%, Monthly Cost: ${c['cost_monthly']:.2f} [{idle_tag}]{grav_tag}"
                )

        if augmented_storage:
            knowledge_chunks.append("\n**Storage Volumes (EBS):**")
            for s in augmented_storage:
                knowledge_chunks.append(
                    f"- `{s['volume_id']}`: {s['type']}, {s['size_gb']} GB, Cost: ${s['cost_monthly']:.2f}/mo. Action: {s['action']}"
                )

        if augmented_network:
            knowledge_chunks.append("\n**Networking (Elastic IPs):**")
            for net in augmented_network:
                status = "🚨 UNATTACHED ($0.005/hr waste)" if net["is_unattached"] else "Attached"
                knowledge_chunks.append(f"- IP `{net['public_ip']}`: {status}. Potential Savings: ${net['savings']:.2f}/mo")

        if augmented_logs:
            knowledge_chunks.append("\n**CloudWatch Log Groups:**")
            for l in augmented_logs:
                knowledge_chunks.append(f"- `{l['log_group_name']}`: Retention={l['retention_days']}, Stored={l['stored_gb']} GB, Cost=${l['monthly_cost']:.2f}/mo. Action: {l['action']}")

        if augmented_security:
            knowledge_chunks.append("\n**Security Group Ingress Exposure:**")
            for sec in augmented_security:
                if sec["is_publicly_exposed"]:
                    knowledge_chunks.append(f"- 🚨 `{sec['group_id']}` ({sec['group_name']}): World-accessible ports: {sec['high_risk_ports']}")

        # Augment Multi-Account Fleet and FOCUS 1.0 specifications
        fleet_summary = retrieved.get("fleet_summary")
        augmented_fleet = None
        if fleet_summary and fleet_summary.get("total_accounts_registered", 0) > 0:
            augmented_fleet = {
                "total_accounts": fleet_summary.get("total_accounts_registered", 1),
                "total_spend": fleet_summary.get("total_fleet_monthly_spend", 0.0),
                "total_nodes": fleet_summary.get("total_fleet_nodes", 0),
                "total_volumes": fleet_summary.get("total_fleet_volumes", 0),
                "total_eips": fleet_summary.get("total_fleet_eips", 0),
                "total_focus_records": fleet_summary.get("total_focus_records", 0)
            }
            knowledge_chunks.append("\n**Multi-Account Cloud Fleet & FOCUS 1.0 Specification:**")
            knowledge_chunks.append(
                f"- Accounts Monitored: {augmented_fleet['total_accounts']} | Gross Fleet Spend: ${augmented_fleet['total_spend']:.2f}/mo"
            )
            knowledge_chunks.append(
                f"- Fleet Assets: {augmented_fleet['total_nodes']} Compute Nodes, {augmented_fleet['total_volumes']} Disks, {augmented_fleet['total_eips']} EIPs"
            )
            knowledge_chunks.append(
                f"- FOCUS 1.0 Compliance: {augmented_fleet['total_focus_records']} normalized cost lines active"
            )

        # Augment Semantic Policies from Vector Knowledge Store
        semantic_policies = retrieved.get("semantic_policies", [])
        if semantic_policies:
            knowledge_chunks.append("\n**AWS Well-Architected Framework & Enterprise Policy Guidelines:**")
            for p in semantic_policies:
                knowledge_chunks.append(
                    f"- *{p['title']}* (Category: {p.get('category')}, Relevance: {p.get('similarity_score', 0):.2f}):\n  {p['content']}"
                )

        # Augment Real-Time Cost Anomalies
        anomalies = retrieved.get("anomalies", [])
        if anomalies:
            knowledge_chunks.append("\n**Real-Time FinOps Cost Anomalies & Idle Spikes Detected:**")
            for a in anomalies[:4]:
                knowledge_chunks.append(
                    f"- [{a.get('severity', 'HIGH')}] `{a.get('resource_id')}` ({a.get('anomaly_type')}): Monthly Waste ${a.get('financial_impact_monthly', 0.0):.2f}/mo. Root Cause: {a.get('root_cause')}"
                )

        # Augment Spend Forecast & Run-Rate
        forecast = retrieved.get("forecast")
        if forecast:
            knowledge_chunks.append("\n**Predictive Spend Forecast & Budget Trajectory (Holt-Winters):**")
            breach_str = f"EXCEEDED ON DAY {forecast.get('predicted_breach_day')}" if forecast.get("budget_breach_predicted") else "Within Allocated Limit"
            knowledge_chunks.append(
                f"- Daily Run-Rate: ${forecast.get('current_daily_run_rate', 0.0):.2f}/day | Projected Month Total: ${forecast.get('projected_monthly_spend', 0.0):.2f}"
            )
            knowledge_chunks.append(
                f"- Budget: ${forecast.get('monthly_budget', 0.0):.2f} ({forecast.get('budget_utilization_pct', 0.0):.1f}% utilization) -> Risk Status: {breach_str}"
            )

        knowledge_chunks.append(
            f"\n**AGGREGATE QUANTIFIED RECOVERABLE SAVINGS:**\n"
            f"• Monthly Potential Savings: **${total_recoverable_monthly:.2f}/month**\n"
            f"• Annualized Potential Savings: **${total_recoverable_annual:.2f}/year**"
        )

        return {
            "augmented_prompt": "\n".join(knowledge_chunks),
            "total_monthly_savings": total_recoverable_monthly,
            "total_annual_savings": total_recoverable_annual,
            "compute": augmented_compute,
            "storage": augmented_storage,
            "network": augmented_network,
            "security": augmented_security,
            "logs": augmented_logs,
            "fleet": augmented_fleet,
            "semantic_policies": semantic_policies,
            "retrieved_item_count": retrieved.get("total_retrieved_items", 0)
        }

    # =========================================================================
    # 3. GENERATE STAGE
    # =========================================================================
    def ask(self, query: str, inventory: Optional[Dict[str, Any]] = None, use_cache: bool = True) -> Dict[str, Any]:
        """
        Full RAG cycle for user questions:
        Cache Check -> Retrieve -> Augment -> Generate with Groq LLM -> Cache Set.
        """
        inv = self._get_inventory(inventory)
        fingerprint = self._get_inventory_fingerprint(inv)

        if use_cache:
            cached = query_cache.get(query, fingerprint)
            if cached:
                return cached

        retrieved = self.retrieve_context(query=query, inventory=inv)
        augmented = self.augment_context(retrieved, user_query=query)

        sys_prompt = (
            f"{FINOPS_SYSTEM_PROMPT}\n\n"
            f"You have direct real-time access to the user's AWS infrastructure retrieved below.\n"
            f"Base your answers STRICTLY on these actual cloud metrics, instance IDs, and exact calculated figures.\n"
            f"Do not invent fake resources. If an answer requires action, cite the specific resource ID, exact dollars saved, and risk rating."
        )

        user_content = (
            f"REAL-TIME RETRIEVED INFRASTRUCTURE TELEMETRY:\n{augmented['augmented_prompt']}\n\n"
            f"USER INQUIRY:\n{query}"
        )

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_content}
        ]

        result = None
        if self.engine and self.engine.is_available():
            reply = self.engine.chat_completion(messages, max_tokens=1000, temperature=0.2)
            if reply:
                result = {
                    "answer": reply,
                    "provider": "groq",
                    "model": self.engine.active_model,
                    "pipeline": "RAG",
                    "status": "success",
                    "retrieved_domains": retrieved.get("domains", ["all"]),
                    "retrieved_items": retrieved.get("total_retrieved_items", 0),
                    "potential_monthly_savings": augmented["total_monthly_savings"],
                    "semantic_policies": augmented.get("semantic_policies", []),
                    "cached": False
                }

        if not result:
            # Deterministic Grounded Fallback
            fallback_answer = (
                f"### 🤖 Grounded FinOps Analysis (RAG Heuristic Mode)\n\n"
                f"Based on real-time retrieval of your cloud environment ({augmented['retrieved_item_count']} items analyzed):\n\n"
                f"• **Potential Recoverable Spend:** **${augmented['total_monthly_savings']:.2f}/month** (${augmented['total_annual_savings']:.2f}/year)\n"
            )
            for c in augmented["compute"]:
                if c["is_idle"]:
                    fallback_answer += f"• **Idle Compute:** `{c['instance_id']}` ({c['type']}) has average CPU of {c['cpu_avg']}%. {c['suggested_action']}\n"
            for s in augmented["storage"]:
                if s["is_orphaned"]:
                    fallback_answer += f"• **Orphaned Storage:** `{s['volume_id']}` ({s['size_gb']} GB) is unattached. {s['action']}\n"
                elif s["type"] == "gp2":
                    fallback_answer += f"• **gp2 Volume:** `{s['volume_id']}` should be upgraded to gp3. {s['action']}\n"
            for net in augmented["network"]:
                if net["is_unattached"]:
                    fallback_answer += f"• **Unattached Elastic IP:** `{net['public_ip']}` is incurring AWS idle IPv4 fees ($0.005/hr). Release to save $3.60/mo.\n"

            result = {
                "answer": fallback_answer,
                "provider": "deterministic_rag_fallback",
                "model": "rule_engine",
                "pipeline": "RAG",
                "status": "fallback",
                "retrieved_domains": retrieved.get("domains", ["all"]),
                "retrieved_items": retrieved.get("total_retrieved_items", 0),
                "potential_monthly_savings": augmented["total_monthly_savings"],
                "semantic_policies": augmented.get("semantic_policies", []),
                "cached": False
            }

        if use_cache and result:
            query_cache.set(query, result, fingerprint)
        return result

    def generate_recommendations(
        self,
        inventory: Optional[Dict[str, Any]] = None,
        focus_domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generates an executive, multi-vector FinOps Recommendation Report powered by Groq RAG.
        """
        retrieved = self.retrieve_context(inventory=inventory, focus_domain=focus_domain)
        augmented = self.augment_context(retrieved)

        prompt = (
            f"Generate a comprehensive, executive-ready FinOps Cloud Optimization Report based on this live telemetry:\n\n"
            f"{augmented['augmented_prompt']}\n\n"
            f"Structure your report with the following 4 sections:\n"
            f"1. **Executive Briefing & Health Assessment**: High-level synthesis with overall grade and financial impact.\n"
            f"2. **Quick Wins (Zero Downtime / Zero Risk)**: Immediate cleanup of unattached EIPs, orphaned EBS volumes, and uncapped CloudWatch logs with exact savings.\n"
            f"3. **Architectural Rightsizing & Graviton Modernization**: Detailed instance recommendations, before/after monthly costs, and ARM64 migration ROI.\n"
            f"4. **Security & Governance**: Ingress exposure remediation and automated Terraform rollout plan.\n"
            f"Use clean Markdown formatting with bullet points and comparison tables."
        )

        messages = [
            {"role": "system", "content": FINOPS_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        if self.engine and self.engine.is_available():
            reply = self.engine.chat_completion(messages, max_tokens=1400, temperature=0.2)
            if reply:
                return {
                    "report_markdown": reply,
                    "provider": "groq",
                    "model": self.engine.active_model,
                    "monthly_savings": augmented["total_monthly_savings"],
                    "annual_savings": augmented["total_annual_savings"],
                    "items_audited": augmented["retrieved_item_count"],
                    "compute_recommendations": augmented["compute"],
                    "storage_recommendations": augmented["storage"],
                    "network_recommendations": augmented["network"],
                    "security_findings": augmented["security"],
                    "status": "success"
                }

        # Deterministic fallback report
        report_md = (
            f"# 🚀 CloudPulse FinOps Executive Optimization Report\n\n"
            f"**Total Recoverable Spend:** `${augmented['total_monthly_savings']:.2f}/month` "
            f"(`${augmented['total_annual_savings']:.2f}/year`)\n\n"
            f"### ⚡ 1. Quick Wins (Zero Downtime)\n"
        )
        for s in augmented["storage"]:
            if s["is_orphaned"]:
                report_md += f"- **Orphaned EBS Volume `{s['volume_id']}`**: Delete to save **${s['savings']:.2f}/mo**.\n"
        for net in augmented["network"]:
            if net["is_unattached"]:
                report_md += f"- **Unattached Elastic IP `{net['public_ip']}`**: Release to eliminate **${net['savings']:.2f}/mo** idle fee.\n"
        for l in augmented["logs"]:
            if l["is_never_expire"]:
                report_md += f"- **CloudWatch Log Group `{l['log_group_name']}`**: Set 30-day retention to save **${l['savings']:.2f}/mo**.\n"

        report_md += "\n### 🖥️ 2. Architectural Rightsizing & Modernization\n"
        for c in augmented["compute"]:
            if c["is_idle"]:
                report_md += f"- **Idle Instance `{c['instance_id']}` ({c['type']})**: Avg CPU {c['cpu_avg']}%. {c['suggested_action']}.\n"
            elif c.get("graviton_recommendation"):
                g = c["graviton_recommendation"]
                report_md += f"- **Graviton Upgrade for `{c['instance_id']}`**: Switch to `{g['instance_type']}` to save **${g['monthly_savings']:.2f}/mo** ({g['savings_percentage']}).\n"

        report_md += "\n### 🔒 3. Security & Ingress Exposure\n"
        for sec in augmented["security"]:
            if sec["is_publicly_exposed"]:
                report_md += f"- **Vulnerable SG `{sec['group_id']}` ({sec['group_name']})**: Open to world on ports {sec['high_risk_ports']}. {sec['recommendation']}.\n"

        return {
            "report_markdown": report_md,
            "provider": "deterministic_rule_engine",
            "model": "fallback",
            "monthly_savings": augmented["total_monthly_savings"],
            "annual_savings": augmented["total_annual_savings"],
            "items_audited": augmented["retrieved_item_count"],
            "compute_recommendations": augmented["compute"],
            "storage_recommendations": augmented["storage"],
            "network_recommendations": augmented["network"],
            "security_findings": augmented["security"],
            "status": "fallback"
        }


# Global Singleton Pipeline
finops_rag_pipeline = FinOpsRAGPipeline()
