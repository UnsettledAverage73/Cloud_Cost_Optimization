import logging
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy import text
try:
    from database.connection import sync_engine, SyncSessionLocal
    from database.models import (
        Base, Organization, ConnectedAWSAccount, CloudResource,
        ResourceTelemetry, DailySpendRecord, OptimizationFinding, RemediationAuditLedger,
        Schedule, ScheduledJob
    )
except ImportError:
    from backend.database.connection import sync_engine, SyncSessionLocal
    from backend.database.models import (
        Base, Organization, ConnectedAWSAccount, CloudResource,
        ResourceTelemetry, DailySpendRecord, OptimizationFinding, RemediationAuditLedger,
        Schedule, ScheduledJob
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("cloudpulse.init_db")

def initialize_database():
    """Initializes tables and configures TimescaleDB hypertables."""
    logger.info("Connecting to database and creating relational tables...")
    Base.metadata.create_all(bind=sync_engine)

    with sync_engine.connect() as conn:
        # Check TimescaleDB extension
        has_timescale = False
        try:
            ext_check = conn.execute(
                text("SELECT extversion FROM pg_extension WHERE extname='timescaledb';")
            ).scalar()
            if not ext_check:
                logger.info("Attempting to enable TimescaleDB extension...")
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"))
                conn.commit()
            has_timescale = True
        except Exception as e:
            logger.warning(f"TimescaleDB extension not installed on this PostgreSQL instance (running in standard PostgreSQL mode): {e}")

        if has_timescale:
            # Convert resource_telemetry to hypertable
            try:
                conn.execute(text(
                    "SELECT create_hypertable('resource_telemetry', 'time', "
                    "chunk_time_interval => INTERVAL '7 days', if_not_exists => TRUE);"
                ))
                conn.commit()
                logger.info("Configured 'resource_telemetry' as TimescaleDB hypertable.")
            except Exception as e:
                logger.warning(f"Note on resource_telemetry hypertable: {e}")

            # Convert daily_spend_records to hypertable
            try:
                conn.execute(text(
                    "SELECT create_hypertable('daily_spend_records', 'time', "
                    "chunk_time_interval => INTERVAL '30 days', if_not_exists => TRUE);"
                ))
                conn.commit()
                logger.info("Configured 'daily_spend_records' as TimescaleDB hypertable.")
            except Exception as e:
                logger.warning(f"Note on daily_spend_records hypertable: {e}")
        else:
            logger.info("Standard PostgreSQL tables created with composite indexes.")

    logger.info("Database schema & hypertables successfully initialized.")

def seed_demo_data():
    """Seeds initial demo organization, account, resources, spend records, and telemetry."""
    session = SyncSessionLocal()
    try:
        # Check if organization exists
        org = session.query(Organization).first()
        if not org:
            org = Organization(
                name="Acme Corp Global",
                plan_tier="enterprise"
            )
            session.add(org)
            session.flush()
            logger.info(f"Created demo organization: {org.name} ({org.id})")

        # Check if connected account exists
        account = session.query(ConnectedAWSAccount).filter_by(organization_id=org.id).first()
        if not account:
            account = ConnectedAWSAccount(
                organization_id=org.id,
                account_id="123456789012",
                account_name="Production AWS Master",
                role_arn="arn:aws:iam::123456789012:role/CloudPulseFinOpsRole",
                external_id="cp-sec-9a8b7c6d5e4f3a2b",
                auth_method="assume_role",
                regions=["us-east-1", "us-west-2", "eu-west-1"],
                status="active"
            )
            session.add(account)
            session.flush()
            logger.info(f"Created demo account: {account.account_name} ({account.id})")

        # Check if resources exist
        res_count = session.query(CloudResource).filter_by(account_id=account.id).count()
        if res_count == 0:
            demo_resources = [
                CloudResource(
                    account_id=account.id,
                    resource_id="i-036358db85d245e3a",
                    service="ec2",
                    region="us-east-1",
                    resource_type="t3.micro",
                    name="api-gateway-prod",
                    state="running",
                    monthly_cost=12.40,
                    tags={"Environment": "production", "Owner": "platform-team", "Project": "core-api"},
                    configuration={"instance_type": "t3.micro", "vcpu": 2, "memory_gb": 1.0, "architecture": "x86_64"}
                ),
                CloudResource(
                    account_id=account.id,
                    resource_id="i-09f81a2b3c4d5e6f7",
                    service="ec2",
                    region="us-east-1",
                    resource_type="m5.2xlarge",
                    name="ml-training-worker",
                    state="running",
                    monthly_cost=277.40,
                    tags={"Environment": "dev", "Owner": "ai-team"},
                    configuration={"instance_type": "m5.2xlarge", "vcpu": 8, "memory_gb": 32.0, "architecture": "x86_64"}
                ),
                CloudResource(
                    account_id=account.id,
                    resource_id="vol-0992817361abce",
                    service="ebs",
                    region="us-east-1",
                    resource_type="gp2",
                    name="orphaned-legacy-backup",
                    state="available",
                    monthly_cost=10.00,
                    tags={"Environment": "staging"},
                    configuration={"size_gb": 100, "volume_type": "gp2", "iops": 300},
                    is_orphaned=True
                ),
                CloudResource(
                    account_id=account.id,
                    resource_id="eipalloc-01928374859a",
                    service="eip",
                    region="us-east-1",
                    resource_type="ElasticIP",
                    name="unattached-bastion-ip",
                    state="unassociated",
                    monthly_cost=3.60,
                    tags={},
                    configuration={"public_ip": "54.210.12.3"},
                    is_orphaned=True
                ),
                CloudResource(
                    account_id=account.id,
                    resource_id="rds-analytics-prod",
                    service="rds",
                    region="us-east-1",
                    resource_type="db.r5.xlarge",
                    name="analytics-read-replica",
                    state="available",
                    monthly_cost=350.40,
                    tags={"Environment": "dev", "Team": "data"},
                    configuration={"multi_az": True, "engine": "postgres", "allocated_storage": 250}
                )
            ]
            session.add_all(demo_resources)
            session.flush()
            logger.info("Added demo cloud resources.")

        # Seed Daily Spend (FOCUS 1.0 Aligned)
        spend_count = session.query(DailySpendRecord).filter_by(account_id=account.id).count()
        if spend_count == 0:
            now = datetime.now(timezone.utc)
            spend_records = []
            services_data = [
                ("AmazonEC2", 18.50, 15.20),
                ("AmazonRDS", 14.80, 12.10),
                ("AmazonS3", 4.20, 3.90),
                ("AmazonVPC", 3.10, 3.10),
                ("CloudWatch", 1.80, 1.80),
            ]
            # Seed past 14 days of spend
            for day_offset in range(14, -1, -1):
                day_time = (now - timedelta(days=day_offset)).replace(hour=0, minute=0, second=0, microsecond=0)
                # Introduce a realistic spike 3 days ago for EC2 to test anomaly detection
                multiplier = 2.8 if day_offset == 3 else (1.0 + (14 - day_offset) * 0.02)
                for svc, billed, effective in services_data:
                    billed_day = billed * (multiplier if svc == "AmazonEC2" else 1.0)
                    spend_records.append(
                        DailySpendRecord(
                            time=day_time,
                            account_id=account.id,
                            service_name=svc,
                            charge_category="Usage",
                            region="us-east-1",
                            billed_cost=round(billed_day, 4),
                            effective_cost=round(effective * multiplier if svc == "AmazonEC2" else effective, 4)
                        )
                    )
            session.add_all(spend_records)
            session.flush()
            logger.info(f"Seeded {len(spend_records)} FOCUS daily spend records.")

        # Seed High-Frequency Telemetry
        telemetry_count = session.query(ResourceTelemetry).filter_by(account_id=account.id).count()
        if telemetry_count == 0:
            now = datetime.now(timezone.utc)
            telemetry_records = []
            # Seed 24 hours of hourly metrics for the instances
            for hour_offset in range(24, -1, -1):
                metric_time = now - timedelta(hours=hour_offset)
                # api-gateway-prod has moderate CPU
                telemetry_records.append(
                    ResourceTelemetry(
                        time=metric_time,
                        resource_id="i-036358db85d245e3a",
                        account_id=account.id,
                        metric_name="CPUUtilization",
                        val_avg=14.5,
                        val_max=28.2,
                        val_p95=22.0
                    )
                )
                # ml-training-worker is idle (<2% CPU)
                telemetry_records.append(
                    ResourceTelemetry(
                        time=metric_time,
                        resource_id="i-09f81a2b3c4d5e6f7",
                        account_id=account.id,
                        metric_name="CPUUtilization",
                        val_avg=1.8,
                        val_max=3.2,
                        val_p95=2.4
                    )
                )
            session.add_all(telemetry_records)
            session.flush()
            logger.info(f"Seeded {len(telemetry_records)} TimescaleDB telemetry points.")

        # Seed Findings
        finding_count = session.query(OptimizationFinding).filter_by(account_id=account.id).count()
        if finding_count == 0:
            demo_findings = [
                OptimizationFinding(
                    id="find-idle-ec2-m5",
                    organization_id=org.id,
                    account_id=account.id,
                    resource_id="i-09f81a2b3c4d5e6f7",
                    category="Compute",
                    title="Downsize Idle EC2 m5.2xlarge -> t4g.medium",
                    description="Instance CPU average is 1.8% over 14 days. Modernize to Graviton t4g.medium for 88% savings.",
                    monthly_savings=243.80,
                    effort="Quick Win",
                    action_type="downsize_ec2",
                    status="open",
                    iac_pr_url=None
                ),
                OptimizationFinding(
                    id="find-orphan-vol-099",
                    organization_id=org.id,
                    account_id=account.id,
                    resource_id="vol-0992817361abce",
                    category="Storage",
                    title="Prune Detached gp2 EBS Volume (100 GB)",
                    description="Volume unattached for >30 days. Safe snapshot will be taken before cleanup.",
                    monthly_savings=10.00,
                    effort="Quick Win",
                    action_type="delete_orphaned_volume",
                    status="open",
                    iac_pr_url=None
                ),
                OptimizationFinding(
                    id="find-unattached-eip",
                    organization_id=org.id,
                    account_id=account.id,
                    resource_id="eipalloc-01928374859a",
                    category="Network",
                    title="Release Unassociated Elastic IP",
                    description="Elastic IP 54.210.12.3 is incurring $0.005/hr unattached reservation fee.",
                    monthly_savings=3.60,
                    effort="Quick Win",
                    action_type="release_elastic_ip",
                    status="open",
                    iac_pr_url=None
                ),
                OptimizationFinding(
                    id="find-rds-multi-az-dev",
                    organization_id=org.id,
                    account_id=account.id,
                    resource_id="rds-analytics-prod",
                    category="Database",
                    title="Convert Dev/Test Multi-AZ RDS to Single-AZ",
                    description="Dev tagged database running expensive redundant standby replica.",
                    monthly_savings=175.20,
                    effort="Architectural",
                    action_type="rds_single_az",
                    status="open",
                    iac_pr_url=None
                )
            ]
            session.add_all(demo_findings)
            session.flush()
            logger.info("Added demo optimization findings.")

        session.commit()
        logger.info("Seed data committed successfully!")
    except Exception as e:
        session.rollback()
        logger.error(f"Error seeding database: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    initialize_database()
