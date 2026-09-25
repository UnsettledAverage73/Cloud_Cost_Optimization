"""
CloudPulse FOCUS 1.0 & DuckDB Lakehouse Domain API Router
High-performance in-memory OLAP analytics over FinOps Open Cost & Usage Specification datasets.
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException

try:
    from database.connection import SyncSessionLocal
    from database.models import DailySpendRecord
    from engines.focus_spec import FOCUSNormalizer
    from engines.focus_lakehouse import focus_lakehouse
    from core.state import get_realtime_store
except ImportError:
    from backend.database.connection import SyncSessionLocal
    from backend.database.models import DailySpendRecord
    from backend.engines.focus_spec import FOCUSNormalizer
    from backend.engines.focus_lakehouse import focus_lakehouse
    from backend.core.state import get_realtime_store

router = APIRouter(prefix="/api/v2/focus", tags=["FOCUS 1.0 Lakehouse"])


def _get_live_inventory():
    """Helper to retrieve inventory from shared realtime store."""
    return get_realtime_store()


@router.get("/spend")
async def get_focus_spend(limit: int = 100):
    """
    Returns spend records adhering to the FinOps FOCUS 1.0 standard
    partitioned in the TimescaleDB hypertable 'daily_spend_records'.
    """
    session = SyncSessionLocal()
    try:
        records = session.query(DailySpendRecord).order_by(
            DailySpendRecord.time.desc(), DailySpendRecord.billed_cost.desc()
        ).limit(limit).all()

        total_billed = sum(float(r.billed_cost) for r in records)
        total_effective = sum(float(r.effective_cost) for r in records)

        return {
            "specification": "FOCUS 1.0",
            "count": len(records),
            "summary": {
                "total_billed_cost": round(total_billed, 2),
                "total_effective_cost": round(total_effective, 2)
            },
            "records": [r.to_dict() for r in records]
        }
    except Exception as e:
        # Fallback to in-memory Lakehouse
        spend_rows = focus_lakehouse.get_spend_by_service() if focus_lakehouse else []
        return {
            "specification": "FOCUS 1.0 (In-Memory Fallback)",
            "count": len(spend_rows),
            "records": spend_rows
        }
    finally:
        session.close()


@router.post("/query")
async def execute_focus_sql_query(payload: dict):
    """Executes high-throughput SQL analytics over FOCUS 1.0 datasets in DuckDB."""
    sql = payload.get("query")
    if not sql:
        raise HTTPException(status_code=400, detail="SQL query is required")

    db = _get_live_inventory()
    if db:
        focus_records = FOCUSNormalizer.normalize_inventory(db)
        focus_lakehouse.load_focus_records(focus_records)

    try:
        result = focus_lakehouse.execute_query(sql)
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/analytics")
async def get_focus_analytics():
    """Returns pre-aggregated FOCUS 1.0 analytics (by service, account, and top cost drivers)."""
    db = _get_live_inventory()
    if db:
        focus_records = FOCUSNormalizer.normalize_inventory(db)
        focus_lakehouse.load_focus_records(focus_records)

    return {
        "status": "success",
        "spend_by_service": focus_lakehouse.get_spend_by_service(),
        "spend_by_account": focus_lakehouse.get_spend_by_account(),
        "top_cost_drivers": focus_lakehouse.get_top_cost_drivers(limit=10)
    }
