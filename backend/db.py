from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "crm.db"
SQL_PATH = BASE_DIR / "crm.sql"


def _normalize_sql_script(sql_text: str) -> str:
    script = sql_text
    script = script.replace("CREATE DATABASE crm_ai;", "")
    script = script.replace("USE crm_ai;", "")
    script = script.replace("INT PRIMARY KEY AUTO_INCREMENT", "INTEGER PRIMARY KEY AUTOINCREMENT")
    script = script.replace("AUTO_INCREMENT", "AUTOINCREMENT")
    script = script.replace("DECIMAL(10,2)", "REAL")
    script = script.replace("DECIMAL(10, 2)", "REAL")
    script = script.replace("DATETIME DEFAULT CURRENT_TIMESTAMP", "DATETIME DEFAULT CURRENT_TIMESTAMP")
    script = script.replace("\r\n", "\n")
    return script.strip() + "\n"


def initialize_database() -> None:
    if DB_PATH.exists():
        return

    if not SQL_PATH.exists():
        raise FileNotFoundError(f"SQL file not found: {SQL_PATH}")

    sql_text = SQL_PATH.read_text(encoding="utf-8")
    script = _normalize_sql_script(sql_text)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(script)
    conn.commit()
    conn.close()


def get_connection() -> sqlite3.Connection:
    initialize_database()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def get_schema_context() -> str:
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        context = "DATABASE: crm_ai\n"
        for table_row in tables:
            table_name = table_row["name"]
            columns = conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
            context += f"\nTABLE: {table_name}\n"
            for col in columns:
                col_name = col[1]
                col_type = col[2] or "TEXT"
                nullable = "YES" if col[3] == 0 else "NO"
                context += f"   {col_name} ({col_type}) NULLABLE={nullable}\n"

            foreign_keys = conn.execute(f"PRAGMA foreign_key_list('{table_name}')").fetchall()
            if foreign_keys:
                context += "   FOREIGN KEYS:\n"
                for fk in foreign_keys:
                    context += (
                        f"     {table_name}.{fk[3]} -> {fk[2]}.{fk[4]}\n"
                    )

        context += "\nRELATIONSHIPS:\n"
        for table_row in tables:
            table_name = table_row["name"]
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list('{table_name}')").fetchall()
            for fk in foreign_keys:
                context += f"{table_name}.{fk[3]} -> {fk[2]}.{fk[4]}\n"
        return context.strip() + "\n"
    finally:
        conn.close()


def get_dataset_overview() -> dict[str, Any]:
    conn = get_connection()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()

        tables_info: list[dict[str, Any]] = []
        for table_row in tables:
            name = table_row["name"]
            columns = conn.execute(f"PRAGMA table_info('{name}')").fetchall()
            count = conn.execute(f"SELECT COUNT(*) FROM \"{name}\"").fetchone()[0]

            columns_info = []
            for col in columns:
                col_name = col[1]
                col_type = col[2] or "TEXT"
                null_count = conn.execute(
                    f"SELECT COUNT(*) FROM \"{name}\" WHERE \"{col_name}\" IS NULL"
                ).fetchone()[0]
                columns_info.append(
                    {
                        "name": col_name,
                        "type": col_type,
                        "nullable": not bool(col[3]),
                        "null_count": null_count,
                    }
                )

            tables_info.append(
                {
                    "table_name": name,
                    "row_count": count,
                    "columns": columns_info,
                }
            )

        relationships = []
        for table_row in tables:
            table_name = table_row["name"]
            foreign_keys = conn.execute(f"PRAGMA foreign_key_list('{table_name}')").fetchall()
            for fk in foreign_keys:
                relationships.append(
                    {
                        "from_table": table_name,
                        "from_column": fk[3],
                        "to_table": fk[2],
                        "to_column": fk[4],
                    }
                )

        return {
            "database_name": "crm_ai",
            "tables": tables_info,
            "relationships": relationships,
            "summary": {
                "total_tables": len(tables_info),
                "total_rows": sum(item["row_count"] for item in tables_info),
            },
        }
    finally:
        conn.close()


def get_sample_questions() -> list[str]:
    return [
        "Show all customers from Kerala",
        "Show top 5 customers by revenue",
        "List customers who purchased Laptop Pro",
        "Show pending orders",
        "Which products are selling the most by quantity?",
        "Show lead distribution by source",
        "Which sales rep has the highest revenue?",
    ]
