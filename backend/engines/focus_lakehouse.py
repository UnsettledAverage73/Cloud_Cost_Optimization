"""
CloudPulse In-Memory FOCUS 1.0 Lakehouse Query Engine
Provides high-throughput SQL analytics over FOCUS 1.0 standardized cost datasets.
Uses embedded DuckDB for zero-copy Parquet and in-memory analytics with automatic SQLite fallback.
Enables sub-millisecond filtering, aggregation by service/account/region, and custom SQL analytics.
"""

import time
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

try:
    import duckdb
    _HAS_DUCKDB = True
except ImportError:
    import sqlite3
    _HAS_DUCKDB = False

logger = logging.getLogger("finops.engines.lakehouse")


class FOCUSLakehouse:
    """
    High-performance in-memory SQL analytics engine implementing
    FinOps Open Cost & Usage Specification (FOCUS 1.0).
    Powered by DuckDB with automatic SQLite3 fallback.
    """

    def __init__(self):
        self.engine_type = "duckdb" if _HAS_DUCKDB else "sqlite3"
        if _HAS_DUCKDB:
            self.conn = duckdb.connect(":memory:")
        else:
            self.conn = sqlite3.connect(":memory:", check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        cursor = self.conn.cursor()
        if self.engine_type == "duckdb":
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS focus_costs (
                    ChargePeriodStart VARCHAR,
                    ChargePeriodEnd VARCHAR,
                    BillingAccountId VARCHAR,
                    SubAccountId VARCHAR,
                    ProviderName VARCHAR,
                    RegionName VARCHAR,
                    ServiceName VARCHAR,
                    ServiceCategory VARCHAR,
                    ResourceID VARCHAR,
                    ResourceName VARCHAR,
                    ResourceType VARCHAR,
                    EffectiveCost DOUBLE,
                    ListCost DOUBLE,
                    BilledCost DOUBLE,
                    UsageQuantity DOUBLE,
                    UsageUnit VARCHAR,
                    PricingQuantity DOUBLE,
                    PricingUnit VARCHAR,
                    Currency VARCHAR
                )
            """)
            try:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_service ON focus_costs(ServiceName)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_category ON focus_costs(ServiceCategory)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_account ON focus_costs(BillingAccountId)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_provider ON focus_costs(ProviderName)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_resource ON focus_costs(ResourceID)")
            except Exception:
                pass  # DuckDB doesn't strictly require explicit indexes for small-to-medium tables
        else:
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
                    ServiceCategory TEXT,
                    ResourceID TEXT,
                    ResourceName TEXT,
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
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_focus_category ON focus_costs(ServiceCategory)")
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
            service_name = r.get("ServiceName") or r.get("Service", "Compute")
            service_cat = r.get("ServiceCategory") or r.get("Category")
            if not service_cat:
                try:
                    from engines.focus_spec import FOCUSNormalizer
                    service_cat = FOCUSNormalizer._map_service_category(service_name)
                except Exception:
                    service_cat = "Compute" if "compute" in service_name.lower() or "ec2" in service_name.lower() else "Other"

            rows.append((
                r.get("ChargePeriodStart"),
                r.get("ChargePeriodEnd"),
                r.get("BillingAccountId") or r.get("AccountId"),
                r.get("SubAccountId") or r.get("BillingAccountId"),
                r.get("ProviderName", "AWS"),
                r.get("RegionName") or r.get("Region", "us-east-1"),
                service_name,
                service_cat,
                r.get("ResourceID") or r.get("ResourceId", "unknown"),
                r.get("ResourceName") or r.get("ResourceID") or r.get("ResourceId", "unknown"),
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
                ProviderName, RegionName, ServiceName, ServiceCategory, ResourceID,
                ResourceName, ResourceType,
                EffectiveCost, ListCost, BilledCost, UsageQuantity, UsageUnit,
                PricingQuantity, PricingUnit, Currency
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        if hasattr(self.conn, "commit"):
            try:
                self.conn.commit()
            except Exception:
                pass
        logger.info(f"Loaded {len(rows)} FOCUS 1.0 records into {self.engine_type} in-memory lakehouse.")

    def load_parquet(self, parquet_path: Union[str, Path], clear_existing: bool = True) -> int:
        """
        Directly loads a CUR 2.0 or FOCUS 1.0 Parquet file (or directory of parquet files)
        into the lakehouse using DuckDB's zero-copy read_parquet.
        """
        if not _HAS_DUCKDB:
            raise RuntimeError("DuckDB is required for direct Parquet ingestion.")

        p = Path(parquet_path)
        path_str = str(p / "*.parquet") if p.is_dir() else str(p)

        cursor = self.conn.cursor()
        if clear_existing:
            cursor.execute("DELETE FROM focus_costs")

        # Discover schema of the parquet file
        cols_info = self.conn.execute(f"DESCRIBE SELECT * FROM read_parquet('{path_str}') LIMIT 1").fetchall()
        col_names = [c[0] for c in cols_info]

        if "EffectiveCost" in col_names and "ServiceName" in col_names and "ResourceID" in col_names:
            # Native FOCUS 1.0 parquet schema
            if "ServiceCategory" in col_names and "ResourceName" in col_names:
                cursor.execute(f"INSERT INTO focus_costs SELECT * FROM read_parquet('{path_str}')")
            else:
                cat_expr = '"ServiceCategory"' if "ServiceCategory" in col_names else "'Compute' as ServiceCategory"
                name_expr = '"ResourceName"' if "ResourceName" in col_names else '"ResourceID" as ResourceName'
                cursor.execute(f"""
                    INSERT INTO focus_costs (
                        ChargePeriodStart, ChargePeriodEnd, BillingAccountId, SubAccountId,
                        ProviderName, RegionName, ServiceName, ServiceCategory, ResourceID,
                        ResourceName, ResourceType,
                        EffectiveCost, ListCost, BilledCost, UsageQuantity, UsageUnit,
                        PricingQuantity, PricingUnit, Currency
                    )
                    SELECT
                        ChargePeriodStart, ChargePeriodEnd, BillingAccountId, SubAccountId,
                        ProviderName, RegionName, ServiceName, {cat_expr}, ResourceID,
                        {name_expr}, ResourceType,
                        EffectiveCost, ListCost, BilledCost, UsageQuantity, UsageUnit,
                        PricingQuantity, PricingUnit, Currency
                    FROM read_parquet('{path_str}')
                """)
        else:
            # Map AWS CUR 2.0 schema
            cost_col = next((c for c in ["EffectiveCost", "lineItem/UnblendedCost", "lineItem/NetUnblendedCost", "BilledCost", "cost"] if c in col_names), None)
            res_col = next((c for c in ["ResourceId", "ResourceID", "lineItem/ResourceId", "resource_id"] if c in col_names), None)
            prod_col = next((c for c in ["ServiceName", "lineItem/ProductCode", "ProductCode", "service"] if c in col_names), None)
            type_col = next((c for c in ["ResourceType", "product/instanceType", "instance_type"] if c in col_names), None)

            cost_expr = f'COALESCE(TRY_CAST("{cost_col}" AS DOUBLE), 0.0)' if cost_col else "0.0"
            res_expr = f'COALESCE("{res_col}", \'unknown\')' if res_col else "'unknown'"
            prod_expr = f'COALESCE("{prod_col}", \'Cloud Service\')' if prod_col else "'Cloud Service'"
            type_expr = f'COALESCE("{type_col}", \'Resource\')' if type_col else "'Resource'"

            query = f"""
                INSERT INTO focus_costs (
                    ChargePeriodStart, ChargePeriodEnd, BillingAccountId, SubAccountId,
                    ProviderName, RegionName, ServiceName, ServiceCategory, ResourceID,
                    ResourceName, ResourceType,
                    EffectiveCost, ListCost, BilledCost, UsageQuantity, UsageUnit,
                    PricingQuantity, PricingUnit, Currency
                )
                SELECT
                    CURRENT_TIMESTAMP as ChargePeriodStart,
                    CURRENT_TIMESTAMP as ChargePeriodEnd,
                    'cur-account' as BillingAccountId,
                    'cur-account' as SubAccountId,
                    'AWS' as ProviderName,
                    'us-east-1' as RegionName,
                    {prod_expr} as ServiceName,
                    'Compute' as ServiceCategory,
                    {res_expr} as ResourceID,
                    {res_expr} as ResourceName,
                    {type_expr} as ResourceType,
                    {cost_expr} as EffectiveCost,
                    {cost_expr} as ListCost,
                    {cost_expr} as BilledCost,
                    1.0 as UsageQuantity,
                    'Hours' as UsageUnit,
                    1.0 as PricingQuantity,
                    'Hours' as PricingUnit,
                    'USD' as Currency
                FROM read_parquet('{path_str}')
            """
            cursor.execute(query)

        count_res = self.conn.execute("SELECT COUNT(*) FROM focus_costs").fetchone()
        loaded_count = count_res[0] if count_res else 0
        logger.info(f"Successfully ingested {loaded_count} lines from Parquet {path_str} into DuckDB.")
        return loaded_count

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
            "engine": self.engine_type,
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
