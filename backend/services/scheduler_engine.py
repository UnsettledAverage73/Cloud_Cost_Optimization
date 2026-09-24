import asyncio
import logging
import uuid
from datetime import datetime, time, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

try:
    from database.connection import SyncSessionLocal, ping_database
    from database.models import Schedule, ScheduledJob
except Exception:
    try:
        from backend.database.connection import SyncSessionLocal, ping_database
        from backend.database.models import Schedule, ScheduledJob
    except Exception:
        SyncSessionLocal = None
        ping_database = lambda: False
        Schedule = None
        ScheduledJob = None

try:
    from remediation.guardian import GuardianValidator
    from remediation.actions import SafeRemediationExecutor
except Exception:
    try:
        from backend.remediation.guardian import GuardianValidator
        from backend.remediation.actions import SafeRemediationExecutor
    except Exception:
        GuardianValidator = None
        SafeRemediationExecutor = None

logger = logging.getLogger("finops.scheduler.engine")


class SchedulerEngine:
    """
    OptiScale Central Operational Scheduler & Pre-Warming Engine.
    Evaluates instance on/off windows, handles 10-minute grace periods,
    validates safety through Guardian, and dispatches boto3/remediation execution.
    """

    def __init__(self):
        self._is_running = False
        self._worker_task: Optional[asyncio.Task] = None
        # In-memory stores for resilience / offline mode
        self._memory_schedules: Dict[str, Dict[str, Any]] = {}
        self._memory_jobs: List[Dict[str, Any]] = []
        # Strictly realtime: no hardcoded demo schedules seeded

    # -------------------------------------------------------------
    # Schedule CRUD
    # -------------------------------------------------------------
    def list_schedules(self) -> List[Dict[str, Any]]:
        """Lists all configured schedules from PostgreSQL or in-memory fallback."""
        try:
            if ping_database():
                with SyncSessionLocal() as session:
                    db_scheds = session.query(Schedule).all()
                    if db_scheds:
                        return [s.to_dict() for s in db_scheds]
        except Exception as e:
            logger.debug(f"DB read schedules fallback to memory: {e}")

        return list(self._memory_schedules.values())

    def create_or_update_schedule(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Creates or updates an operational schedule."""
        sched_id = str(data.get("id") or uuid.uuid4())
        instance_id = data.get("instance_id")
        if not instance_id:
            raise ValueError("instance_id is required")

        record = {
            "id": sched_id,
            "instance_id": instance_id,
            "organization_id": data.get("organization_id"),
            "timezone": data.get("timezone", "Asia/Kolkata"),
            "start_time": data.get("start_time", "08:00"),
            "stop_time": data.get("stop_time", "20:00"),
            "monday": bool(data.get("monday", True)),
            "tuesday": bool(data.get("tuesday", True)),
            "wednesday": bool(data.get("wednesday", True)),
            "thursday": bool(data.get("thursday", True)),
            "friday": bool(data.get("friday", True)),
            "saturday": bool(data.get("saturday", False)),
            "sunday": bool(data.get("sunday", False)),
            "prewarm_minutes": int(data.get("prewarm_minutes", 15)),
            "grace_period_minutes": int(data.get("grace_period_minutes", 10)),
            "enabled": bool(data.get("enabled", True)),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Save to DB if online
        try:
            if ping_database():
                with SyncSessionLocal() as session:
                    existing = session.query(Schedule).filter(Schedule.id == uuid.UUID(sched_id)).first() if "sched-" not in sched_id else None
                    if not existing:
                        db_model = Schedule(
                            id=uuid.UUID(sched_id) if "sched-" not in sched_id else uuid.uuid4(),
                            instance_id=record["instance_id"],
                            timezone=record["timezone"],
                            start_time=record["start_time"],
                            stop_time=record["stop_time"],
                            monday=record["monday"],
                            tuesday=record["tuesday"],
                            wednesday=record["wednesday"],
                            thursday=record["thursday"],
                            friday=record["friday"],
                            saturday=record["saturday"],
                            sunday=record["sunday"],
                            prewarm_minutes=record["prewarm_minutes"],
                            grace_period_minutes=record["grace_period_minutes"],
                            enabled=record["enabled"],
                        )
                        session.add(db_model)
                    else:
                        for k, v in record.items():
                            if k not in ["id", "created_at", "updated_at"]:
                                setattr(existing, k, v)
                    session.commit()
        except Exception as e:
            logger.debug(f"DB save schedule fallback to memory: {e}")

        self._memory_schedules[sched_id] = record
        return record

    def delete_schedule(self, schedule_id: str) -> bool:
        """Deletes a schedule."""
        removed = False
        try:
            if ping_database():
                with SyncSessionLocal() as session:
                    session.query(Schedule).filter(Schedule.id == uuid.UUID(schedule_id)).delete()
                    session.commit()
                    removed = True
        except Exception:
            pass

        if schedule_id in self._memory_schedules:
            del self._memory_schedules[schedule_id]
            removed = True
        return removed

    # -------------------------------------------------------------
    # Jobs Management & Audit
    # -------------------------------------------------------------
    def list_jobs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves list of scheduled execution jobs (realtime only, excludes mock demo instance)."""
        try:
            if ping_database():
                with SyncSessionLocal() as session:
                    db_jobs = (
                        session.query(ScheduledJob)
                        .filter(ScheduledJob.instance_id != "i-0a1b2c3d4e5f60718")
                        .order_by(ScheduledJob.scheduled_at.desc())
                        .limit(limit)
                        .all()
                    )
                    if db_jobs:
                        return [j.to_dict() for j in db_jobs]
        except Exception as e:
            logger.debug(f"DB read jobs fallback to memory: {e}")

        clean_mem = [
            j for j in self._memory_jobs
            if j.get("instance_id") != "i-0a1b2c3d4e5f60718"
        ]
        sorted_mem = sorted(
            clean_mem,
            key=lambda x: x.get("scheduled_at", ""),
            reverse=True
        )
        return sorted_mem[:limit]

    def _record_job(self, job_dict: Dict[str, Any]):
        """Persists a job to memory and DB."""
        # Update or append in memory
        found = False
        for i, existing in enumerate(self._memory_jobs):
            if existing.get("id") == job_dict.get("id"):
                self._memory_jobs[i] = job_dict
                found = True
                break
        if not found:
            self._memory_jobs.append(job_dict)

        # Persist to DB if possible
        try:
            if ping_database():
                with SyncSessionLocal() as session:
                    job_uuid = uuid.UUID(job_dict["id"]) if isinstance(job_dict["id"], str) and len(job_dict["id"]) == 36 else uuid.uuid4()
                    db_job = session.query(ScheduledJob).filter(ScheduledJob.id == job_uuid).first()
                    if not db_job:
                        db_job = ScheduledJob(
                            id=job_uuid,
                            instance_id=job_dict["instance_id"],
                            action=job_dict["action"],
                            scheduled_at=datetime.fromisoformat(job_dict["scheduled_at"].replace("Z", "+00:00")),
                            status=job_dict.get("status", "PENDING"),
                            reason=job_dict.get("reason"),
                            blocked_reason=job_dict.get("blocked_reason"),
                            execution_details=job_dict.get("execution_details", {}),
                            executed_at=datetime.fromisoformat(job_dict["executed_at"].replace("Z", "+00:00")) if job_dict.get("executed_at") else None,
                        )
                        session.add(db_job)
                    else:
                        db_job.status = job_dict.get("status", db_job.status)
                        db_job.blocked_reason = job_dict.get("blocked_reason", db_job.blocked_reason)
                        db_job.execution_details = job_dict.get("execution_details", db_job.execution_details)
                        if job_dict.get("executed_at"):
                            db_job.executed_at = datetime.fromisoformat(job_dict["executed_at"].replace("Z", "+00:00"))
                    session.commit()
        except Exception as e:
            logger.debug(f"DB persist job note: {e}")

    # -------------------------------------------------------------
    # Time Evaluation Logic
    # -------------------------------------------------------------
    @classmethod
    def _is_day_active(cls, schedule: Dict[str, Any], weekday_idx: int) -> bool:
        # weekday(): Monday is 0 and Sunday is 6
        day_keys = [
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        ]
        return bool(schedule.get(day_keys[weekday_idx], False))

    @classmethod
    def _parse_time_str(cls, t_str: str) -> Tuple[int, int]:
        parts = t_str.strip().split(":")
        return int(parts[0]), int(parts[1])

    def _has_recent_job(
        self,
        instance_id: str,
        action: str,
        statuses: Optional[List[str]] = None,
        window_minutes: int = 15
    ) -> bool:
        """Checks if a job was already dispatched for this instance & action recently to prevent duplicate spam."""
        recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        for job in self.list_jobs(limit=100):
            if job.get("instance_id") == instance_id and job.get("action") == action:
                if statuses and job.get("status") not in statuses:
                    continue
                time_str = job.get("scheduled_at") or job.get("created_at")
                if time_str:
                    try:
                        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                        if dt >= recent_cutoff:
                            return True
                    except Exception:
                        pass
        return False

    def evaluate_schedules(
        self,
        now_dt: Optional[datetime] = None,
        force_action: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Evaluates active schedules against current time.
        Determines if an instance should START, PREWARM, enter NOTIFYING (10-min grace), or STOP.
        Prevents duplicate alerts through recent-window deduplication.
        """
        now_utc = now_dt or datetime.now(timezone.utc)
        generated_jobs = []

        schedules = self.list_schedules()
        for sched in schedules:
            if not sched.get("enabled", True):
                continue

            tz_str = sched.get("timezone", "Asia/Kolkata")
            try:
                tz = ZoneInfo(tz_str)
            except Exception:
                tz = ZoneInfo("UTC")

            local_dt = now_utc.astimezone(tz)
            weekday_idx = local_dt.weekday()

            if not self._is_day_active(sched, weekday_idx):
                continue

            instance_id = sched["instance_id"]
            start_h, start_m = self._parse_time_str(sched.get("start_time", "08:00"))
            stop_h, stop_m = self._parse_time_str(sched.get("stop_time", "20:00"))

            today_start = local_dt.replace(hour=start_h, minute=start_m, second=0, microsecond=0)
            today_stop = local_dt.replace(hour=stop_h, minute=stop_m, second=0, microsecond=0)

            prewarm_lead = timedelta(minutes=sched.get("prewarm_minutes", 15))
            prewarm_trigger = today_start - prewarm_lead

            grace_lead = timedelta(minutes=sched.get("grace_period_minutes", 10))
            grace_trigger = today_stop - grace_lead

            # Window check: within ±3 minutes of trigger with deduplication
            # 1. PREWARM trigger
            if abs((local_dt - prewarm_trigger).total_seconds()) <= 180:
                if not self._has_recent_job(instance_id, "PREWARM", window_minutes=20):
                    job = self._create_job_dict(
                        sched, "PREWARM", local_dt, "Predictive Pre-Warming lead time initiated"
                    )
                    generated_jobs.append(job)

            # 2. START trigger
            elif abs((local_dt - today_start).total_seconds()) <= 180:
                if not self._has_recent_job(instance_id, "START", window_minutes=20):
                    job = self._create_job_dict(
                        sched, "START", local_dt, "Scheduled business start time reached"
                    )
                    generated_jobs.append(job)

            # 3. NOTIFYING (Grace period alert)
            elif abs((local_dt - grace_trigger).total_seconds()) <= 180:
                if not self._has_recent_job(instance_id, "STOP", statuses=["NOTIFYING", "OVERRIDDEN", "EXECUTING", "SUCCESS"], window_minutes=20):
                    job = self._create_job_dict(
                        sched, "STOP", local_dt, "10-minute pre-stop grace period initiated",
                        initial_status="NOTIFYING"
                    )
                    generated_jobs.append(job)
                    try:
                        try:
                            from services.notification_engine import notification_engine
                        except ImportError:
                            from backend.services.notification_engine import notification_engine
                        notification_engine.dispatch_event("grace_period", {"job": job})
                    except Exception as notif_err:
                        logger.debug(f"Grace period notification notice: {notif_err}")

            # 4. STOP trigger
            elif abs((local_dt - today_stop).total_seconds()) <= 180:
                if not self._has_recent_job(instance_id, "STOP", statuses=["PENDING", "EXECUTING", "SUCCESS"], window_minutes=20):
                    job = self._create_job_dict(
                        sched, "STOP", local_dt, "Scheduled evening shutdown window reached",
                        initial_status="PENDING"
                    )
                    generated_jobs.append(job)

        return generated_jobs

    def _create_job_dict(
        self,
        sched: Dict[str, Any],
        action: str,
        scheduled_at: datetime,
        reason: str,
        initial_status: str = "PENDING"
    ) -> Dict[str, Any]:
        job_id = str(uuid.uuid4())
        return {
            "id": job_id,
            "schedule_id": sched.get("id"),
            "instance_id": sched["instance_id"],
            "action": action,
            "scheduled_at": scheduled_at.astimezone(timezone.utc).isoformat(),
            "status": initial_status,
            "reason": reason,
            "blocked_reason": None,
            "execution_details": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "executed_at": None,
        }

    # -------------------------------------------------------------
    # Full Execution Pipeline (Guardian -> Safe Executor)
    # -------------------------------------------------------------
    async def process_job(
        self,
        job: Dict[str, Any],
        session=None,
        tags: Optional[Dict[str, str]] = None,
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Takes a pending job through:
        1. Guardian Validator
        2. Status: VALIDATING -> APPROVED or BLOCKED
        3. SafeRemediationExecutor -> Boto3 execution
        4. Status: EXECUTING -> SUCCESS or FAILED
        """
        instance_id = job["instance_id"]
        action = job["action"]
        job["status"] = "VALIDATING"
        self._record_job(job)

        # Step 1: Run Guardian Validator
        is_safe, reason, details = await GuardianValidator.guardian_check(
            instance_id=instance_id,
            action=action,
            tags=tags,
            session=session
        )

        job["execution_details"]["guardian_checks"] = details

        if not is_safe:
            job["status"] = "BLOCKED"
            job["blocked_reason"] = reason
            self._record_job(job)
            logger.info(f"🛑 Guardian blocked job {job['id']} on {instance_id}: {reason}")
            return job

        # Step 2: Mark APPROVED and EXECUTING
        job["status"] = "EXECUTING"
        self._record_job(job)

        # Step 3: Execute via SafeRemediationExecutor
        try:
            executor = SafeRemediationExecutor(session=session)
            # Map action to executor method name
            action_key = "stop" if action == "STOP" else "start"
            exec_res = executor.execute(
                action=action_key,
                resource_id=instance_id,
                dry_run=dry_run,
                tags=tags
            )

            job["execution_details"]["executor_result"] = exec_res
            job["executed_at"] = datetime.now(timezone.utc).isoformat()

            if exec_res.get("success"):
                job["status"] = "SUCCESS"
            else:
                job["status"] = "FAILED"
                job["blocked_reason"] = exec_res.get("message", "Execution failed")

        except Exception as err:
            logger.error(f"Error executing scheduled job {job['id']}: {err}")
            job["status"] = "FAILED"
            job["blocked_reason"] = str(err)

        self._record_job(job)
        return job

    # -------------------------------------------------------------
    # User Override / Grace Period Actions
    # -------------------------------------------------------------
    def override_job(
        self,
        job_id: str,
        override_type: str = "KEEP_RUNNING",
        extension_hours: int = 2
    ) -> Dict[str, Any]:
        """
        Allows developer/operator to click [KEEP RUNNING] or [STOP NOW]
        during the 10-minute grace period. Checks memory and PostgreSQL database.
        """
        target_job = None
        for job in self._memory_jobs:
            if job.get("id") == job_id:
                target_job = job
                break

        # Check DB if not found in memory
        if not target_job and ping_database():
            try:
                with SyncSessionLocal() as session:
                    job_uuid = uuid.UUID(job_id) if isinstance(job_id, str) and len(job_id) == 36 else None
                    if job_uuid:
                        db_j = session.query(ScheduledJob).filter(ScheduledJob.id == job_uuid).first()
                        if db_j:
                            target_job = db_j.to_dict()
                            self._memory_jobs.append(target_job)
            except Exception as e:
                logger.debug(f"DB lookup failed: {e}")

        if not target_job:
            raise ValueError(f"Job {job_id} not found")

        override_upper = override_type.upper().strip()
        instance_id = target_job.get("instance_id")

        if override_upper in ["KEEP_RUNNING", "OVERRIDE"]:
            target_job["status"] = "OVERRIDDEN"
            until_time = datetime.now(timezone.utc) + timedelta(hours=extension_hours)
            target_job["reason"] = f"Overridden by developer: Keep running for {extension_hours}h (until {until_time.strftime('%H:%M UTC')})"
            target_job["execution_details"]["override_until"] = until_time.isoformat()
            self._record_job(target_job)

            # Clear/override all other duplicate NOTIFYING alerts for this instance
            for other in self._memory_jobs:
                if other.get("instance_id") == instance_id and other.get("status") == "NOTIFYING":
                    other["status"] = "OVERRIDDEN"
                    self._record_job(other)

            return {
                "success": True,
                "job": target_job,
                "message": f"Instance {instance_id} will remain running for {extension_hours} hours."
            }

        elif override_upper in ["STOP_NOW", "IMMEDIATE"]:
            target_job["status"] = "PENDING"
            target_job["reason"] = "Developer bypassed grace period: Stop requested immediately"
            self._record_job(target_job)

            # Clear other duplicate NOTIFYING alerts for this instance
            for other in self._memory_jobs:
                if other.get("id") != target_job.get("id") and other.get("instance_id") == instance_id and other.get("status") == "NOTIFYING":
                    other["status"] = "CANCELLED"
                    self._record_job(other)

            return {
                "success": True,
                "job": target_job,
                "message": f"Instance {instance_id} stop queued for immediate Guardian validation."
            }

        else:
            raise ValueError(f"Unknown override type '{override_type}'")

    # -------------------------------------------------------------
    # Asynchronous Loop Worker
    # -------------------------------------------------------------
    async def run_scheduler_tick(self, session=None, dry_run: bool = False):
        """Single tick of the background scheduler (evaluates and processes due jobs)."""
        new_jobs = self.evaluate_schedules()
        for job in new_jobs:
            self._record_job(job)
            if job["status"] == "PENDING":
                await self.process_job(job, session=session, dry_run=dry_run)

    async def _worker_loop(self):
        logger.info("OptiScale Scheduling background loop started.")
        while self._is_running:
            try:
                await self.run_scheduler_tick(dry_run=False)
            except Exception as e:
                logger.error(f"Error in scheduler tick: {e}")
            await asyncio.sleep(60)

    def start_worker(self):
        if not self._is_running:
            self._is_running = True
            self._worker_task = asyncio.create_task(self._worker_loop())
            logger.info("Background scheduler worker launched.")

    def stop_worker(self):
        if self._is_running:
            self._is_running = False
            if self._worker_task:
                self._worker_task.cancel()
            logger.info("Background scheduler worker stopped.")


# Singleton instance
scheduler_engine = SchedulerEngine()
