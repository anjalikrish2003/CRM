from __future__ import annotations

import os
import sqlite3
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from google import genai
from groq import Groq

from backend.db import get_connection, get_schema_context

load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

GEMINI_CLIENT = None
gemini_api_key = os.getenv("GEMINI_API_KEY")
if gemini_api_key:
    GEMINI_CLIENT = genai.Client(api_key=gemini_api_key)

GROQ_CLIENT = None
groq_api_key = os.getenv("GROQ_API_KEY")
if groq_api_key:
    GROQ_CLIENT = Groq(api_key=groq_api_key)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")


def _normalize_sql(sql: str) -> str:
    cleaned = sql.strip()
    cleaned = cleaned.replace("```sql", "").replace("```", "").strip()
    cleaned = cleaned.rstrip(";") + ";"
    return cleaned


def _generate_model_response(prompt: str) -> str:
    failures: list[str] = []

    if GROQ_CLIENT is not None:
        try:
            response = GROQ_CLIENT.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            content = response.choices[0].message.content
            if content and content.strip():
                return content.strip()
            failures.append("Groq returned an empty response")
        except Exception as exc:
            failures.append(f"Groq ({type(exc).__name__})")

    if GEMINI_CLIENT is not None:
        try:
            response = GEMINI_CLIENT.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            if response.text and response.text.strip():
                return response.text.strip()
            failures.append("Gemini returned an empty response")
        except Exception as exc:
            failures.append(f"Gemini ({type(exc).__name__})")

    if GROQ_CLIENT is None and GEMINI_CLIENT is None:
        raise RuntimeError(
            "Natural-language database questions require GROQ_API_KEY or GEMINI_API_KEY."
        )
    raise RuntimeError(
        "The configured AI services could not generate a database query: "
        + ", ".join(failures)
        + ". Please try again later."
    )


def generate_sql(
    question: str,
    previous_sql: str | None = None,
    database_error: str | None = None,
) -> str:
    schema_context = get_schema_context()
    prompt = f"""
    You are an expert SQLite analyst answering questions about a CRM database.
    DATABASE SCHEMA:
    {schema_context}
    RULES:
    1. Translate the user's question into one executable SQLite SELECT query.
    2. Use only the tables and columns in the schema. Do not invent fields or relationships.
    3. Use joins only when required and follow the listed foreign keys.
    4. Never use data-changing statements, PRAGMA, ATTACH, or multiple statements.
    5. Return only SQL, without markdown or an explanation.
    USER QUESTION:
    {question}
    """
    if previous_sql and database_error:
        prompt += f"""
        The previous query failed. Correct it while preserving the user's request.
        FAILED QUERY: {previous_sql}
        DATABASE ERROR: {database_error}
        """

    return _normalize_sql(_generate_model_response(prompt))


def validate_sql(sql: str) -> None:
    text = sql.lower().strip()
    forbidden = [
        "drop ", "truncate ", "delete ", "update ", "insert ", "alter ", "create ",
        "grant ", "revoke ", "attach ", "detach ", "replace ", "execute ",
    ]
    if not text.startswith("select") and not text.startswith("with "):
        raise ValueError("Only SELECT queries are allowed for analytics. No data changes are permitted.")
    for token in forbidden:
        if token in text:
            raise ValueError(f"Query blocked: disallowed SQL operation detected ({token.strip()}).")


def _chart_payload(df: pd.DataFrame, question: str) -> dict[str, Any] | None:
    if df is None or df.empty:
        return None

    cols = list(df.columns)
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    metric_cols = [
        c for c in numeric_cols
        if not c.lower().endswith("_id") and c.lower() not in {"id"}
    ]
    categorical_cols = [c for c in cols if c not in numeric_cols and not pd.api.types.is_numeric_dtype(df[c])]

    if categorical_cols and metric_cols:
        x_key = categorical_cols[0]
        y_key = metric_cols[0]
        if "date" in x_key.lower() or "created" in x_key.lower() or "order_date" in x_key.lower():
            return {
                "type": "line",
                "title": question,
                "x_key": x_key,
                "y_key": y_key,
                "x_values": df[x_key].astype(str).tolist(),
                "y_values": df[y_key].round(2).tolist(),
            }
        if len(df) <= 12:
            return {
                "type": "bar",
                "title": question,
                "x_key": x_key,
                "y_key": y_key,
                "x_values": df[x_key].astype(str).tolist(),
                "y_values": df[y_key].round(2).tolist(),
            }
        return {
            "type": "horizontalBar",
            "title": question,
            "x_key": x_key,
            "y_key": y_key,
            "x_values": df[x_key].astype(str).tolist(),
            "y_values": df[y_key].round(2).tolist(),
        }

    if len(metric_cols) >= 2:
        x_key, y_key = metric_cols[0], metric_cols[1]
        return {
            "type": "scatter",
            "title": question,
            "x_key": x_key,
            "y_key": y_key,
            "x_values": df[x_key].round(2).tolist(),
            "y_values": df[y_key].round(2).tolist(),
        }

    if len(df.columns) >= 1 and not numeric_cols:
        series = df.iloc[:, 0].value_counts().reset_index()
        series.columns = ["label", "count"]
        return {
            "type": "pie",
            "title": question,
            "x_key": "label",
            "y_key": "count",
            "x_values": series["label"].astype(str).tolist(),
            "y_values": series["count"].tolist(),
        }

    return None


def _format_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 2)
    return value


def explain_results(question: str, df: pd.DataFrame) -> str:
    if df.empty:
        return f"No records matched '{question}' in the available CRM data."

    if len(df) == 1 and len(df.columns) == 1:
        column = str(df.columns[0])
        value = df.iloc[0, 0]
        if pd.api.types.is_number(value):
            operation = "value"
            column_lower = column.lower()
            if "avg" in column_lower or "average" in column_lower:
                operation = "average"
            elif "count" in column_lower:
                operation = "count"
            elif "sum" in column_lower or "total" in column_lower:
                operation = "total"
            elif "min" in column_lower:
                operation = "minimum"
            elif "max" in column_lower:
                operation = "maximum"
            return f"The {operation} is {_format_value(value)}."
        return f"For '{question}', the result is {value}."

    numeric_columns = [
        column
        for column in df.columns
        if pd.api.types.is_numeric_dtype(df[column])
        and not str(column).lower().endswith("_id")
    ]
    if len(df) == 1:
        return f"For '{question}', one matching record is shown in the table below."
    if numeric_columns:
        metric = numeric_columns[0]
        label_columns = [column for column in df.columns if column not in numeric_columns]
        if label_columns:
            top = df.loc[df[metric].idxmax()]
            return (
                f"Found {len(df)} results. The highest {metric} is "
                f"{_format_value(top[metric])} for {top[label_columns[0]]}."
            )
    return f"Found {len(df)} results. The matching data is shown in the table below."


def execute_question(question: str) -> dict[str, Any]:
    sql = generate_sql(question)
    conn = get_connection()
    conn.execute("PRAGMA query_only = ON")
    try:
        for attempt in range(2):
            validate_sql(sql)
            try:
                df = pd.read_sql_query(sql, conn)
                break
            except sqlite3.Error as exc:
                if attempt == 1:
                    return {
                        "question": question,
                        "sql": sql,
                        "answer": (
                            "I couldn't answer that question with the available database schema. "
                            f"The database reported: {exc}"
                        ),
                        "chart": None,
                        "table": {"columns": [], "rows": []},
                        "insights": "Try rephrasing the question or asking about a listed table or column.",
                        "success": False,
                    }
                sql = generate_sql(question, previous_sql=sql, database_error=str(exc))
    finally:
        conn.close()

    df = df.fillna("")
    table_rows = [
        {key: _format_value(value) for key, value in row.items()}
        for _, row in df.iterrows()
    ]

    chart = _chart_payload(df, question)
    answer = explain_results(question, df)

    return {
        "question": question,
        "sql": sql,
        "answer": answer,
        "chart": chart,
        "table": {
            "columns": list(df.columns),
            "rows": table_rows,
        },
        "insights": answer,
        "success": True,
    }
