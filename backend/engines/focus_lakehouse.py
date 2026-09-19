"""
CloudPulse In-Memory FOCUS 1.0 Lakehouse Query Engine
Provides high-throughput SQL analytics over FOCUS 1.0 standardized cost datasets.
Enables sub-millisecond filtering, aggregation by service/account/region, and custom SQL analytics.
"""

import sqlite3
import time
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("finops.engines.lakehouse")


class FOCUSLakehouse:
    """
    In-memory SQL analytics engine implementing FinOps Open Cost & Usage Specification (FOCUS 1.0).
    """

    def __init__(self):
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS focus_costs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ChargePeriodStart TEXT,
                ChargePeriodEnd TEXT,
                BillingAccountId TEXT,
                SubAccountId TEXT,
                ProviderName TEXT,
                RegionName TEXT,
                ServiceName TEXT,
                ResourceID TEXT,
                ResourceType TEXT,
                EffectiveCost REAL,
                ListCost REAL,
                BilledCost REAL,
                UsageQuantity REAL,
                UsageUnit TEXT,
                PricingQuantity REAL,
                PricingUnit TEXT,
                Currency TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_service ON focus_costs(ServiceName)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_account ON focus_costs(BillingAccountId)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_provider ON focus_costs(ProviderName)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_resource ON focus_costs(ResourceID)")
        self.conn.commit()

    def load_focus_records(self, records: List[Dict[str, Any]], clear_existing: bool = True):
        """Loads normalized FOCUS 1.0 records into the in-memory lakehouse table."""
        cursor = self.conn.cursor()
        if clear_existing:
            cursor.execute("DELETE FROM focus_costs")

        rows = []
        for r in records:
            rows.append((
                r.get("ChargePeriodStart"),
                r.get("ChargePeriodEnd"),
                r.get("BillingAccountId") or r.get("AccountId"),
                r.get("SubAccountId") or r.get("BillingAccountId"),
                r.get("ProviderName", "AWS"),
                r.get("RegionName") or r.get("Region", "us-east-1"),
                r.get("ServiceName") or r.get("Service", "Compute"),
                r.get("ResourceID") or r.get("ResourceId", "unknown"),
                r.get("ResourceType", "Instance"),
                float(r.get("EffectiveCost", r.get("Cost", 0.0)) or 0.0),
                float(r.get("ListCost", r.get("EffectiveCost", 0.0)) or 0.0),
                float(r.get("BilledCost", r.get("EffectiveCost", 0.0)) or 0.0),
                float(r.get("UsageQuantity", 1.0) or 1.0),
                r.get("UsageUnit", "Hours"),
                float(r.get("PricingQuantity", 1.0) or 1.0),
                r.get("PricingUnit", "Hours"),
                r.get("Currency", "USD"),
            ))

        cursor.executemany("""
            INSERT INTO focus_costs (
                ChargePeriodStart, ChargePeriodEnd, BillingAccountId, SubAccountId,
                ProviderName, RegionName, ServiceName, ResourceID, ResourceType,
                EffectiveCost, ListCost, BilledCost, UsageQuantity, UsageUnit,
                PricingQuantity, PricingUnit, Currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        self.conn.commit()
        logger.info(f"Loaded {len(rows)} FOCUS 1.0 records into in-memory lakehouse.")

    def execute_query(self, sql_query: str) -> Dict[str, Any]:
        """
        Executes an arbitrary read-only SQL query against the focus_costs table.
        Enforces read-only safety checks.
        """
        clean_sql = sql_query.strip()
        lower_sql = clean_sql.lower()
        if not (lower_sql.startswith("select") or lower_sql.startswith("with")):
            raise ValueError("Only SELECT or WITH queries are permitted on the FOCUS lakehouse.")

        start_time = time.perf_counter()
        cursor = self.conn.cursor()
        cursor.execute(clean_sql)
        rows = cursor.fetchall()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        columns = [d[0] for d in cursor.description] if cursor.description else []
        result_rows = [dict(zip(columns, row)) for row in rows]

        return {
            "query": clean_sql,
            "columns": columns,
            "row_count": len(result_rows),
            "execution_time_ms": elapsed_ms,
            "rows": result_rows
        }

    def get_spend_by_service(self) -> List[Dict[str, Any]]:
        """Returns consolidated monthly spend grouped by cloud service."""
        sql = """
            SELECT ServiceName, 
                   ROUND(SUM(EffectiveCost), 2) as TotalEffectiveCost,
                   COUNT(ResourceID) as ResourceCount,
                   ProviderName
            FROM focus_costs
            GROUP BY ServiceName, ProviderName
            ORDER BY TotalEffectiveCost DESC
        """
        return self.execute_query(sql)["rows"]

    def get_spend_by_account(self) -> List[Dict[str, Any]]:
        """Returns consolidated monthly spend grouped by billing account."""
        sql = """
            SELECT BillingAccountId, 
                   ROUND(SUM(EffectiveCost), 2) as TotalSpend,
                   COUNT(DISTINCT ServiceName) as DistinctServices,
                   COUNT(ResourceID) as TotalResources
            FROM focus_costs
            GROUP BY BillingAccountId
            ORDER BY TotalSpend DESC
        """
        return self.execute_query(sql)["rows"]

    def get_top_cost_drivers(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns top cost driver resources across the enterprise fleet."""
        sql = f"""
            SELECT ResourceID, ResourceType, ServiceName, RegionName, 
                   ROUND(EffectiveCost, 2) as MonthlySpend,
                   ProviderName
            FROM focus_costs
            ORDER BY EffectiveCost DESC
            LIMIT {int(limit)}
        """
        return self.execute_query(sql)["rows"]


# Global Singleton
focus_lakehouse = FOCUSLakehouse()
