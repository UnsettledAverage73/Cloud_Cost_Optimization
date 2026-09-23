import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Boolean, Numeric, Float, BigInteger,
    DateTime, ForeignKey, JSON, Index, PrimaryKeyConstraint, Text
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
try:
    from database.connection import Base
except ImportError:
    from backend.database.connection import Base

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    plan_tier = Column(String(50), default="enterprise", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    accounts = relationship("ConnectedAWSAccount", back_populates="organization", cascade="all, delete-orphan")
    findings = relationship("OptimizationFinding", back_populates="organization", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": str(self.id),
            "name": self.name,
            "plan_tier": self.plan_tier,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class ConnectedAWSAccount(Base):
    __tablename__ = "connected_aws_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(String(12), nullable=False)
    account_name = Column(String(255), nullable=False)
    role_arn = Column(String(512), nullable=False)
    external_id = Column(String(128), nullable=False)
    auth_method = Column(String(50), default="assume_role", nullable=False)  # 'assume_role', 'keys', 'learner_lab'
    regions = Column(JSONB, default=["us-east-1"], nullable=False)
    status = Column(String(50), default="active", nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="accounts")
    resources = relationship("CloudResource", back_populates="account", cascade="all, delete-orphan")
    findings = relationship("OptimizationFinding", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_org_account", "organization_id", "account_id", unique=True),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "organization_id": str(self.organization_id),
            "account_id": self.account_id,
            "account_name": self.account_name,
            "role_arn": self.role_arn,
            "external_id": self.external_id,
            "auth_method": self.auth_method,
            "regions": self.regions,
            "status": self.status,
            "last_synced_at": self.last_synced_at.isoformat() if self.last_synced_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class CloudResource(Base):
    __tablename__ = "cloud_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    account_id = Column(UUID(as_uuid=True), ForeignKey("connected_aws_accounts.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(String(255), nullable=False)
    service = Column(String(50), nullable=False)  # 'ec2', 'ebs', 's3', 'rds', 'nat', 'eip', 'alb'
    region = Column(String(50), nullable=False)
    resource_type = Column(String(100), nullable=False)
    name = Column(String(255), nullable=True)
    state = Column(String(50), nullable=True)
    monthly_cost = Column(Numeric(10, 2), default=0.00, nullable=False)
    tags = Column(JSONB, default={}, nullable=False)
    configuration = Column(JSONB, default={}, nullable=False)
    is_orphaned = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    account = relationship("ConnectedAWSAccount", back_populates="resources")

    __table_args__ = (
        Index("idx_account_resource", "account_id", "resource_id", unique=True),
        Index("idx_res_service_region", "service", "region"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "account_id": str(self.account_id),
            "resource_id": self.resource_id,
            "service": self.service,
            "region": self.region,
            "resource_type": self.resource_type,
            "name": self.name,
            "state": self.state,
            "monthly_cost": float(self.monthly_cost) if self.monthly_cost is not None else 0.0,
            "tags": self.tags,
            "configuration": self.configuration,
            "is_orphaned": self.is_orphaned,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ResourceTelemetry(Base):
    """TimescaleDB Hypertable for high-frequency cloud metrics."""
    __tablename__ = "resource_telemetry"

    time = Column(DateTime(timezone=True), nullable=False)
    resource_id = Column(String(255), nullable=False)
    account_id = Column(UUID(as_uuid=True), nullable=False)
    metric_name = Column(String(100), nullable=False)  # 'CPUUtilization', 'NetworkIn', 'DiskReadOps'
    val_avg = Column(Float, nullable=True)
    val_max = Column(Float, nullable=True)
    val_p95 = Column(Float, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("time", "resource_id", "metric_name"),
        Index("idx_telemetry_res_time", "resource_id", "time"),
    )

    def to_dict(self):
        return {
            "time": self.time.isoformat() if self.time else None,
            "resource_id": self.resource_id,
            "account_id": str(self.account_id),
            "metric_name": self.metric_name,
            "val_avg": self.val_avg,
            "val_max": self.val_max,
            "val_p95": self.val_p95
        }


class DailySpendRecord(Base):
    """TimescaleDB Hypertable conforming to FinOps FOCUS 1.0 standard."""
    __tablename__ = "daily_spend_records"

    time = Column(DateTime(timezone=True), nullable=False)
    account_id = Column(UUID(as_uuid=True), nullable=False)
    service_name = Column(String(100), nullable=False)
    charge_category = Column(String(100), default="Usage", nullable=False)
    region = Column(String(50), nullable=False)
    billed_cost = Column(Numeric(12, 4), nullable=False)
    effective_cost = Column(Numeric(12, 4), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("time", "account_id", "service_name", "region"),
        Index("idx_spend_time_svc", "time", "service_name"),
    )

    def to_dict(self):
        return {
            "time": self.time.isoformat() if self.time else None,
            "account_id": str(self.account_id),
            "service_name": self.service_name,
            "charge_category": self.charge_category,
            "region": self.region,
            "billed_cost": float(self.billed_cost),
            "effective_cost": float(self.effective_cost)
        }


class OptimizationFinding(Base):
    __tablename__ = "optimization_findings"

    id = Column(String(255), primary_key=True)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    account_id = Column(UUID(as_uuid=True), ForeignKey("connected_aws_accounts.id", ondelete="CASCADE"), nullable=False)
    resource_id = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False)  # 'Compute', 'Storage', 'Network', 'Database'
    title = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    monthly_savings = Column(Numeric(10, 2), nullable=False)
    effort = Column(String(50), default="Quick Win", nullable=False)  # 'Quick Win', 'Architectural'
    action_type = Column(String(100), nullable=False)
    status = Column(String(50), default="open", nullable=False)  # 'open', 'applied', 'dismissed'
    iac_pr_url = Column(String(512), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    organization = relationship("Organization", back_populates="findings")
    account = relationship("ConnectedAWSAccount", back_populates="findings")

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": str(self.organization_id),
            "account_id": str(self.account_id),
            "resource_id": self.resource_id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "monthly_savings": float(self.monthly_savings),
            "effort": self.effort,
            "action_type": self.action_type,
            "status": self.status,
            "iac_pr_url": self.iac_pr_url,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


class RemediationAuditLedger(Base):
    __tablename__ = "remediation_audit_ledger"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    organization_id = Column(UUID(as_uuid=True), nullable=False)
    action_type = Column(String(100), nullable=False)
    resource_id = Column(String(255), nullable=False)
    operator = Column(String(255), nullable=False)  # 'autonomous_agent', 'admin@user.com'
    is_dry_run = Column(Boolean, nullable=False)
    status = Column(String(50), nullable=False)  # 'success', 'failed', 'simulated'
    safety_snapshot_id = Column(String(255), nullable=True)
    parameters = Column(JSONB, default={}, nullable=False)
    executed_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "organization_id": str(self.organization_id),
            "action_type": self.action_type,
            "resource_id": self.resource_id,
            "operator": self.operator,
            "is_dry_run": self.is_dry_run,
            "status": self.status,
            "safety_snapshot_id": self.safety_snapshot_id,
            "parameters": self.parameters,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }


class Schedule(Base):
    """Central operational schedule defining on/off windows per EC2 instance."""
    __tablename__ = "schedules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id = Column(String(100), nullable=False)
    organization_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    timezone = Column(String(50), default="Asia/Kolkata", nullable=False)

    start_time = Column(String(10), nullable=False, default="08:00")  # HH:MM format
    stop_time = Column(String(10), nullable=False, default="20:00")   # HH:MM format

    monday = Column(Boolean, default=True, nullable=False)
    tuesday = Column(Boolean, default=True, nullable=False)
    wednesday = Column(Boolean, default=True, nullable=False)
    thursday = Column(Boolean, default=True, nullable=False)
    friday = Column(Boolean, default=True, nullable=False)
    saturday = Column(Boolean, default=False, nullable=False)
    sunday = Column(Boolean, default=False, nullable=False)

    prewarm_minutes = Column(BigInteger, default=15, nullable=False)
    grace_period_minutes = Column(BigInteger, default=10, nullable=False)
    enabled = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("idx_schedules_instance", "instance_id"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "instance_id": self.instance_id,
            "organization_id": str(self.organization_id) if self.organization_id else None,
            "timezone": self.timezone,
            "start_time": self.start_time,
            "stop_time": self.stop_time,
            "monday": self.monday,
            "tuesday": self.tuesday,
            "wednesday": self.wednesday,
            "thursday": self.thursday,
            "friday": self.friday,
            "saturday": self.saturday,
            "sunday": self.sunday,
            "prewarm_minutes": int(self.prewarm_minutes or 15),
            "grace_period_minutes": int(self.grace_period_minutes or 10),
            "enabled": self.enabled,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }


class ScheduledJob(Base):
    """Tracks state lifecycle of each scheduled optimization request."""
    __tablename__ = "scheduled_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_id = Column(UUID(as_uuid=True), ForeignKey("schedules.id", ondelete="SET NULL"), nullable=True)
    instance_id = Column(String(100), nullable=False)
    action = Column(String(30), nullable=False)  # 'START', 'STOP', 'PREWARM', 'RESIZE'
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(30), default="PENDING", nullable=False)
    # PENDING, NOTIFYING, OVERRIDDEN, VALIDATING, APPROVED, EXECUTING, SUCCESS, BLOCKED, FAILED, CANCELLED
    reason = Column(Text, nullable=True)
    blocked_reason = Column(Text, nullable=True)
    execution_details = Column(JSONB, default={}, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    executed_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_scheduled_jobs_status", "status", "scheduled_at"),
        Index("idx_scheduled_jobs_instance", "instance_id", "created_at"),
    )

    def to_dict(self):
        return {
            "id": str(self.id),
            "schedule_id": str(self.schedule_id) if self.schedule_id else None,
            "instance_id": self.instance_id,
            "action": self.action,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "status": self.status,
            "reason": self.reason,
            "blocked_reason": self.blocked_reason,
            "execution_details": self.execution_details,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None
        }

