import re
import logging
from typing import Dict, Any, List
from sqlalchemy import text
try:
    from database.connection import sync_engine
except ImportError:
    from backend.database.connection import sync_engine

logger = logging.getLogger("cloudpulse.copilot.tools.sql")

FORBIDDEN_KEYWORDS = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]

def execute_readonly_sql(sql_query: str) -> Dict[str, Any]:
    """
    Executes a read-only SQL query against the TimescaleDB / PostgreSQL database.
    Strictly forbids mutating queries to maintain enterprise safety.
    """
    cleaned = sql_query.strip()
    upper_query = cleaned.upper()

    for kw in FORBIDDEN_KEYWORDS:
        if re.search(rf"\b{kw}\b", upper_query):
            return {
                "success": False,
                "error": f"Security violation: Statement contains forbidden keyword '{kw}'. Only SELECT statements are permitted."
            }

    if not upper_query.startswith("SELECT") and not upper_query.startswith("WITH"):
        return {
            "success": False,
            "error": "Security violation: Query must begin with SELECT or WITH."
        }

    try:
        with sync_engine.connect() as conn:
            result = conn.execute(text(cleaned))
            columns = list(result.keys())
            rows = [dict(zip(columns, [str(v) if not isinstance(v, (int, float, bool, type(None))) else v for v in row])) for row in result.fetchall()]
            return {
                "success": True,
                "row_count": len(rows),
                "columns": columns,
                "data": rows
            }
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return {
            "success": False,
            "error": str(e)
        }

def generate_finops_sql_template(query_type: str, account_id: str = None) -> str:
    """Pre-built optimized queries for standard FinOps reporting."""
    if query_type == "daily_spend_by_service":
        return """
            SELECT time::date AS spend_date, service_name, SUM(billed_cost) AS total_billed
            FROM daily_spend_records
            GROUP BY 1, 2
            ORDER BY 1 DESC, 3 DESC
            LIMIT 30;
        """
    elif query_type == "total_potential_savings":
        return """
            SELECT category, SUM(monthly_savings) AS total_savings, COUNT(*) as finding_count
            FROM optimization_findings
            WHERE status = 'open'
            GROUP BY category
            ORDER BY total_savings DESC;
        """
    elif query_type == "idle_resources":
        return """
            SELECT resource_id, service, resource_type, monthly_cost, is_orphaned
            FROM cloud_resources
            WHERE is_orphaned = TRUE OR monthly_cost > 100
            ORDER BY monthly_cost DESC;
        """
    elif query_type == "recent_telemetry":
        return """
            SELECT resource_id, metric_name, val_avg, val_max, time
            FROM resource_telemetry
            ORDER BY time DESC
            LIMIT 20;
        """
    return "SELECT * FROM daily_spend_records ORDER BY time DESC LIMIT 10;"
