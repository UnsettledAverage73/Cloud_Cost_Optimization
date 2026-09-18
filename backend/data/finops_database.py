import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

DB_PATH = os.getenv("FINOPS_DB_PATH", os.path.join(os.path.dirname(__file__), "finops_ledger.db"))

def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            provider TEXT NOT NULL,
            account_name TEXT NOT NULL,
            auth_method TEXT NOT NULL,
            region TEXT NOT NULL,
            role_arn TEXT,
            access_key_last4 TEXT,
            active INTEGER DEFAULT 0,
            access_mode TEXT DEFAULT \x27live\x27,
            created_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_name TEXT,
            resource_id TEXT UNIQUE NOT NULL,
            resource_type TEXT NOT NULL,
            name TEXT,
            region TEXT,
            state TEXT,
            monthly_cost REAL DEFAULT 0.0,
            metadata_json TEXT,
            updated_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS telemetry (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            instance_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            cpu_utilization REAL,
            mem_used_percent REAL,
            net_in_mb REAL,
            net_out_mb REAL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS spend_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            day TEXT NOT NULL,
            provider TEXT NOT NULL,
            amount REAL NOT NULL,
            currency TEXT DEFAULT \x27USD\x27
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS optimizations (
            id TEXT PRIMARY KEY,
            resource_id TEXT NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            monthly_savings REAL NOT NULL,
            effort TEXT DEFAULT \x27Low\x27,
            action_type TEXT,
            status TEXT DEFAULT \x27pending\x27,
            created_at TEXT NOT NULL,
            applied_at TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS remediation_audit (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            dry_run INTEGER NOT NULL,
            status TEXT NOT NULL,
            details_json TEXT,
            executed_at TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT NOT NULL,
            severity TEXT NOT NULL,
            tone TEXT DEFAULT \x27amber\x27,
            tag TEXT DEFAULT \x27Cost\x27,
            resolved INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()

init_db()

def record_remediation_audit(action: str, resource_id: str, dry_run: bool, status: str, details: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO remediation_audit (action, resource_id, dry_run, status, details_json, executed_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (action, resource_id, 1 if dry_run else 0, status, json.dumps(details), datetime.now(timezone.utc).isoformat()))
    conn.commit()
    conn.close()

def get_remediation_audit_logs(limit: int = 50) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM remediation_audit ORDER BY id DESC LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": row["id"],
            "action": row["action"],
            "resource_id": row["resource_id"],
            "dry_run": bool(row["dry_run"]),
            "status": row["status"],
            "details": json.loads(row["details_json"]) if row["details_json"] else {},
            "executed_at": row["executed_at"],
        }
        for row in rows
    ]

def upsert_optimization(opt: Dict[str, Any]):
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cursor.execute("""
        INSERT INTO optimizations (id, resource_id, type, title, description, monthly_savings, effort, action_type, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title=excluded.title,
            description=excluded.description,
            monthly_savings=excluded.monthly_savings,
            status=excluded.status
    """, (
        opt["id"],
        opt.get("resource_id", opt["id"]),
        opt.get("type", "Cost Optimization"),
        opt["title"],
        opt.get("desc", opt.get("description", "")),
        float(opt.get("savings", opt.get("monthly_savings", 0.0))),
        opt.get("effort", "Low"),
        opt.get("action", opt.get("action_type", "")),
        opt.get("status", "pending"),
        now
    ))
    conn.commit()
    conn.close()

def mark_optimization_applied(opt_id: str, applied: bool = True):
    conn = get_db_connection()
    cursor = conn.cursor()
    status = "applied" if applied else "pending"
    applied_at = datetime.now(timezone.utc).isoformat() if applied else None
    cursor.execute("""
        UPDATE optimizations SET status = ?, applied_at = ? WHERE id = ?
    """, (status, applied_at, opt_id))
    conn.commit()
    conn.close()

def get_all_optimizations() -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM optimizations ORDER BY monthly_savings DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
