"""
CloudPulse Core Production Configuration
Strongly typed configuration management adhering to Google SWE 12-factor standards.
"""

import os
from typing import List, Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # App & Environment
    app_name: str = "CloudPulse FinOps Platform"
    app_version: str = "2.5.0"
    environment: str = Field(default_factory=lambda: os.getenv("ENVIRONMENT", "production"))
    debug: bool = Field(default_factory=lambda: os.getenv("DEBUG", "false").lower() in ("true", "1", "yes"))
    port: int = Field(default_factory=lambda: int(os.getenv("PORT", "8000")))
    host: str = Field(default_factory=lambda: os.getenv("HOST", "0.0.0.0"))

    # Security & CORS
    secret_key: str = Field(default_factory=lambda: os.getenv("SECRET_KEY", "cloudpulse-dev-secret-change-in-prod"))
    allowed_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "https://*.onrender.com",
        "https://*.vercel.app"
    ]

    # Database & Storage
    database_url: Optional[str] = Field(default_factory=lambda: os.getenv("DATABASE_URL"))
    async_database_url: Optional[str] = Field(default_factory=lambda: os.getenv("ASYNC_DATABASE_URL"))
    redis_url: str = Field(default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0"))

    # AI & LLM Inference
    groq_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("GROQ_API_KEY"))
    groq_model: str = Field(default_factory=lambda: os.getenv("GROQ_MODEL", "groq/compound-mini"))
    mistral_api_key: Optional[str] = Field(default_factory=lambda: os.getenv("MISTRAL_API_KEY"))

    # CNCF OpenCost & Kubernetes
    opencost_url: str = Field(default_factory=lambda: os.getenv("OPENCOST_URL", "http://localhost:9003"))
    k8s_cluster_name: str = Field(default_factory=lambda: os.getenv("K8S_CLUSTER_NAME", "eks-prod-us-east-1"))

    # Currency & Localization
    usd_to_inr_rate: float = Field(default_factory=lambda: float(os.getenv("USD_TO_INR_RATE", "84.00")))

    # Notifications
    slack_webhook_url: Optional[str] = Field(default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL"))
    slack_bot_token: Optional[str] = Field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN"))
    slack_app_token: Optional[str] = Field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN"))
    teams_webhook_url: Optional[str] = Field(default_factory=lambda: os.getenv("TEAMS_WEBHOOK_URL"))


settings = Settings()
