"""
CloudPulse Enterprise Semantic Vector Knowledge Base
Enables semantic search over AWS Well-Architected Framework guidelines,
FinOps unit economics, enterprise tagging policies, and modernization playbooks.
"""

import math
import json
import logging
import re
import zlib
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import numpy as np

logger = logging.getLogger("cloudpulse.ai.vector_store")

VECTOR_STORE_DIR = Path.home() / ".cloudpulse"
VECTOR_STORE_FILE = VECTOR_STORE_DIR / "vector_knowledge_store.json"

DEFAULT_FINOPS_POLICIES = [
    {
        "id": "wa-cost-01-idle-compute",
        "title": "AWS Well-Architected: Decommissioning & Rightsizing Idle Compute",
        "category": "well-architected",
        "content": (
            "AWS Well-Architected Cost Optimization Pillar (COST 7): Stop, downsize, or hibernate idle "
            "compute instances. EC2 instances running under 5% average CPU utilization over a 7-day period "
            "should be scheduled to stop during non-business hours or downsized to nano/micro tier. "
            "Savings typically range from 60% to 75% for non-production environments."
        ),
        "tags": ["ec2", "compute", "idle", "downsize", "cost-optimization"]
    },
    {
        "id": "wa-cost-02-graviton-migration",
        "title": "AWS Graviton Architecture Modernization & Efficiency",
        "category": "modernization",
        "content": (
            "AWS Graviton2 and Graviton3 ARM-based processors deliver up to 40% better price performance "
            "over comparable current-generation x86-based instances. Migrating general purpose workloads from "
            "t3.micro or m5.large to t4g.micro or m6g.large yields an immediate 20% on-demand hourly rate reduction "
            "with zero code changes for Linux containers, Python, Node.js, and Java applications."
        ),
        "tags": ["graviton", "arm", "t4g", "ec2", "modernization", "architecture"]
    },
    {
        "id": "wa-cost-03-gp3-storage-upgrade",
        "title": "EBS Volume Modernization: gp2 to gp3 Migration",
        "category": "storage",
        "content": (
            "AWS Elastic Block Store (EBS) General Purpose SSD: Upgrading from gp2 to gp3 provides an immediate "
            "20% cost reduction ($0.08/GB-month vs $0.10/GB-month) while delivering a baseline of 3,000 IOPS and "
            "125 MB/s throughput independent of volume storage size. Upgrades can be performed via AWS Elastic Volumes "
            "without downtime or detachment."
        ),
        "tags": ["ebs", "gp3", "gp2", "storage", "volumes", "iops"]
    },
    {
        "id": "wa-cost-04-unattached-eip-cleanup",
        "title": "Networking: Release Unattached Elastic IPv4 Addresses",
        "category": "networking",
        "content": (
            "Amazon VPC charges $0.005 per hour ($3.65 per month) for every public IPv4 address that is allocated "
            "to an account but not attached to a running EC2 instance or Elastic Network Interface (ENI). "
            "Unattached Elastic IPs represent 100% pure waste and must be released immediately to avoid unnecessary spend."
        ),
        "tags": ["eip", "ipv4", "networking", "vpc", "unattached", "waste"]
    },
    {
        "id": "wa-cost-05-cloudwatch-retention",
        "title": "Observability Cost Guardrails: CloudWatch Log Retention",
        "category": "observability",
        "content": (
            "CloudWatch Logs stores incoming log events indefinitely by default ('Never Expire'), incurring "
            "$0.03 per GB-month in perpetuity. FinOps best practice dictates enforcing a 30-day or 90-day retention "
            "policy on all log groups, archiving older logs to Amazon S3 Standard-IA or Glacier for long-term compliance "
            "at 80%+ lower storage cost."
        ),
        "tags": ["cloudwatch", "logs", "retention", "observability", "s3-glacier"]
    },
    {
        "id": "wa-cost-06-focus-standardization",
        "title": "FinOps Foundation FOCUS 1.0 Standardization Guidelines",
        "category": "focus-standards",
        "content": (
            "The FinOps Open Cost & Usage Specification (FOCUS 1.0) standardizes multi-cloud billing datasets into "
            "uniform schemas. Key dimensions include BillingAccountId, ServiceName, ServiceCategory (Compute, Storage, "
            "Networking, Database), EffectiveCost, BilledCost, PricingCategory, and UsageQuantity. Adhering to FOCUS 1.0 "
            "enables consistent cross-account spend allocation, unit economics, and automated chargeback."
        ),
        "tags": ["focus", "finops", "billing", "governance", "standardization"]
    },
    {
        "id": "wa-cost-07-enterprise-tagging",
        "title": "Enterprise Tagging & Cost Allocation Policy",
        "category": "tagging-policy",
        "content": (
            "All cloud resources must be tagged with four mandatory tags: 'Environment' (prod, staging, dev), "
            "'Owner' (engineering team or lead email), 'CostCenter' (finance GL code), and 'Project' (workload name). "
            "Untagged or incorrectly tagged resources cannot be attributed in FOCUS reports and are automatically "
            "flagged for administrative remediation."
        ),
        "tags": ["tagging", "governance", "costcenter", "allocation", "policy"]
    },
    {
        "id": "wa-cost-08-vpc-endpoint-optimization",
        "title": "VPC Endpoint vs NAT Gateway Data Transfer Optimization",
        "category": "networking",
        "content": (
            "NAT Gateways charge $0.045 per hour plus $0.045 per GB of data processed. High data transfer from private "
            "EC2 instances to Amazon S3 or DynamoDB through a NAT Gateway creates significant cost spikes. Deploying "
            "free Gateway VPC Endpoints for S3 and DynamoDB routes internal traffic across private AWS network circuits, "
            "eliminating 100% of NAT data processing fees."
        ),
        "tags": ["nat-gateway", "vpc-endpoint", "s3", "networking", "data-transfer"]
    }
]


class TextVectorizer:
    """
    High-performance subword and term-frequency vectorizer with L2 normalization.
    Produces deterministic 256-dimensional semantic vectors using numpy.
    Zero external network calls, sub-millisecond execution, and 100% offline reliability.
    """

    def __init__(self, vector_dim: int = 256):
        self.vector_dim = vector_dim

    def _tokenize(self, text: str) -> List[str]:
        cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
        tokens = cleaned.split()
        return [t for t in tokens if len(t) > 1]

    def vectorize(self, text: str) -> np.ndarray:
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self.vector_dim, dtype=np.float32)

        vec = np.zeros(self.vector_dim, dtype=np.float32)
        for i, t in enumerate(tokens):
            # Primary word hash
            h1 = zlib.crc32(t.encode("utf-8")) % self.vector_dim
            vec[h1] += 2.5

            # Bigram hash for phrase-level semantic context
            if i < len(tokens) - 1:
                bigram = f"{t}_{tokens[i+1]}"
                h2 = zlib.crc32(bigram.encode("utf-8")) % self.vector_dim
                vec[h2] += 1.5

            # 3-gram character shingles for prefix/stem matching (e.g. graviton -> grav, iton)
            for j in range(len(t) - 2):
                shingle = t[j:j+3]
                h3 = zlib.crc32(shingle.encode("utf-8")) % self.vector_dim
                vec[h3] += 0.2

        # L2 Normalization to unit length for direct cosine similarity via dot product
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


class VectorKnowledgeStore:
    """
    Enterprise Semantic Vector Knowledge Base:
    - Stores and indexes FinOps guidelines, policies, and AWS Well-Architected docs
    - Performs fast semantic cosine-similarity retrieval
    - Persists state to ~/.cloudpulse/vector_knowledge_store.json
    """

    def __init__(self, vector_dim: int = 256):
        self.vectorizer = TextVectorizer(vector_dim=vector_dim)
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.vectors: Dict[str, np.ndarray] = {}
        self._load_or_bootstrap()

    def _load_or_bootstrap(self):
        """Loads indexed knowledge from disk or bootstraps default FinOps guidelines."""
        loaded = False
        try:
            if VECTOR_STORE_FILE.exists():
                with open(VECTOR_STORE_FILE, "r") as f:
                    data = json.load(f)
                    docs = data.get("documents", {})
                    for doc_id, doc in docs.items():
                        self.documents[doc_id] = doc
                        text_corpus = f"{doc.get('title', '')} {doc.get('content', '')} {' '.join(doc.get('tags', []))}"
                        self.vectors[doc_id] = self.vectorizer.vectorize(text_corpus)
                    if self.documents:
                        loaded = True
                        logger.info(f"Loaded {len(self.documents)} vector documents from disk cache.")
        except Exception as e:
            logger.warning(f"Failed to load vector store from disk: {e}")

        if not loaded:
            self.bootstrap_default_policies()

    def bootstrap_default_policies(self):
        """Indexes curated AWS Well-Architected and FinOps policies."""
        for p in DEFAULT_FINOPS_POLICIES:
            self.add_document(
                doc_id=p["id"],
                title=p["title"],
                content=p["content"],
                category=p["category"],
                tags=p.get("tags", [])
            )
        self.save_to_disk()

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Adds a document and generates its normalized semantic embedding vector."""
        tags = tags or []
        doc = {
            "id": doc_id,
            "title": title,
            "content": content,
            "category": category,
            "tags": tags,
            "metadata": metadata or {}
        }
        self.documents[doc_id] = doc
        text_corpus = f"{title} {content} {' '.join(tags)}"
        self.vectors[doc_id] = self.vectorizer.vectorize(text_corpus)
        logger.debug(f"Indexed vector document: {doc_id}")

    def save_to_disk(self):
        """Persists documents to ~/.cloudpulse/vector_knowledge_store.json."""
        try:
            VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
            with open(VECTOR_STORE_FILE, "w") as f:
                json.dump({"documents": self.documents, "count": len(self.documents)}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save vector store to disk: {e}")

    def search(self, query: str, top_k: int = 3, threshold: float = 0.15) -> List[Dict[str, Any]]:
        """
        Executes semantic cosine-similarity search against indexed policies.
        Returns top-k documents scoring above the similarity threshold.
        """
        if not query or not self.documents:
            return []

        q_vec = self.vectorizer.vectorize(query)
        results = []

        for doc_id, d_vec in self.vectors.items():
            # Cosine similarity between unit vectors is the dot product
            score = float(np.dot(q_vec, d_vec))
            if score >= threshold:
                doc = dict(self.documents[doc_id])
                doc["similarity_score"] = round(score, 4)
                results.append(doc)

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def get_all_documents(self) -> List[Dict[str, Any]]:
        return list(self.documents.values())


# Global Singleton
vector_knowledge_store = VectorKnowledgeStore()
