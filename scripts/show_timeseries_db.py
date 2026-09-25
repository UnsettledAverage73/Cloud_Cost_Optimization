#!/usr/bin/env python3
"""
TimescaleDB Time-Series Inspection Utility for CloudPulse.
Connects to the active PostgreSQL database, verifies TimescaleDB extension,
inspects hypertables and chunk partitions, and prints live telemetry points.
"""

import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text

# Add repo root and backend directory to path
repo_root = Path(__file__).resolve().parent.parent
backend_dir = repo_root / "backend"
for p in [str(repo_root), str(backend_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    try:
        from backend.database.connection import DATABASE_URL
    except Exception:
        DATABASE_URL = "postgresql+psycopg2://postgres:postgrespassword@localhost:5432/cloudpulse_db"

def main():
    print("\n" + "=" * 75)
    print(" 🕒 CLOUDPULSE TIMESCALEDB TIME-SERIES INSPECTOR")
    print("=" * 75)

    # Sanitize URL for logging
    safe_url = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
    print(f"📡 Target DB Host: {safe_url}\n")

    try:
        engine = create_engine(DATABASE_URL, pool_pre_ping=True)
        with engine.connect() as conn:
            # 1. TimescaleDB Extension Check
            res_ext = conn.execute(text("SELECT extversion FROM pg_extension WHERE extname='timescaledb';")).fetchone()
            ext_version = res_ext[0] if res_ext else "Not Installed (Vanilla Postgres)"
            print(f"✅ TimescaleDB Extension Version: {ext_version}")

            # 2. Hypertables Metadata
            print("\n" + "-" * 75)
            print(" 📊 ACTIVE HYPERTABLES & PARTITIONS")
            print("-" * 75)
            hypertables_query = text("""
                SELECT hypertable_name, num_dimensions, num_chunks, compression_enabled
                FROM timescaledb_information.hypertables;
            """)
            try:
                hts = conn.execute(hypertables_query).fetchall()
                print(f" {'Hypertable':<26} | {'Dimensions':<12} | {'Chunks':<8} | {'Compression'}")
                print(" " + "-" * 70)
                for ht in hts:
                    print(f" {ht[0]:<26} | {ht[1]:<12} | {ht[2]:<8} | {ht[3]}")
            except Exception as e:
                print(f" ⚠️  Hypertables query note: {e}")

            # 3. Live In-Guest Telemetry Rows
            print("\n" + "-" * 75)
            print(" ⚡️ LATEST REAL-TIME TELEMETRY (resource_telemetry)")
            print("-" * 75)
            telemetry_query = text("""
                SELECT time, resource_id, metric_name, val_avg, val_max
                FROM resource_telemetry
                ORDER BY time DESC
                LIMIT 8;
            """)
            try:
                rows = conn.execute(telemetry_query).fetchall()
                if rows:
                    print(f" {'Timestamp (UTC)':<22} | {'Resource ID':<22} | {'Metric':<18} | {'Value'}")
                    print(" " + "-" * 70)
                    for r in rows:
                        ts = r[0].strftime('%Y-%m-%d %H:%M:%S') if hasattr(r[0], 'strftime') else str(r[0])
                        print(f" {ts:<22} | {r[1]:<22} | {r[2]:<18} | {r[3]}")
                else:
                    print(" No telemetry points recorded yet.")
            except Exception as e:
                print(f" ⚠️  Telemetry rows note: {e}")

            # 4. TimescaleDB Time-Bucket Aggregation (1-minute rollups)
            print("\n" + "-" * 75)
            print(" 📈 TIMESCALEDB 1-MINUTE TIME-BUCKET ANALYTICS (time_bucket)")
            print("-" * 75)
            bucket_query = text("""
                SELECT time_bucket('1 minute', time) AS bucket,
                       metric_name,
                       ROUND(AVG(val_avg)::numeric, 2) as avg_val,
                       ROUND(MAX(val_max)::numeric, 2) as max_val,
                       COUNT(*) as sample_count
                FROM resource_telemetry
                GROUP BY bucket, metric_name
                ORDER BY bucket DESC
                LIMIT 6;
            """)
            try:
                b_rows = conn.execute(bucket_query).fetchall()
                if b_rows:
                    print(f" {'Time Bucket':<22} | {'Metric':<20} | {'Avg':<8} | {'Max':<8} | {'Samples'}")
                    print(" " + "-" * 70)
                    for b in b_rows:
                        ts = b[0].strftime('%Y-%m-%d %H:%M:%S') if hasattr(b[0], 'strftime') else str(b[0])
                        print(f" {ts:<22} | {b[1]:<20} | {b[2]:<8} | {b[3]:<8} | {b[4]}")
                else:
                    print(" No bucket aggregations available.")
            except Exception as e:
                print(f" ⚠️  Time-bucket query note: {e}")

    except Exception as e:
        print(f"❌ Database connection notice: {e}")

    print("\n" + "=" * 75 + "\n")

if __name__ == "__main__":
    main()
