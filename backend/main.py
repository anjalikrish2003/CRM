from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.requests import Request

from backend.ai import execute_question
from backend.db import get_dataset_overview, get_sample_questions, get_schema_context

BASE_DIR = Path(__file__).resolve().parent.parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

app = FastAPI(title="CRM AI Analytics")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


class ChatRequest(BaseModel):
    question: str


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"request": request},
    )


@app.get("/api/dataset")
async def dataset():
    return get_dataset_overview()


@app.get("/api/sample-questions")
async def sample_questions():
    return {"questions": get_sample_questions()}


@app.get("/api/notebook-insights")
async def notebook_insights():
    return {
        "notebook_name": "crm.ipynb",
        "purpose": "Translate CRM questions into read-only SQL, run them against the CRM database, and return results.",
        "workflow": [
            "Read the database schema and foreign-key relationships dynamically.",
            "Generate a SQL query from the user's CRM question.",
            "Validate the query before execution and return database results.",
            "Explain database errors and retry corrected queries where possible.",
            "Choose a visualization when the result contains categorical and numeric values.",
        ],
        "analysis_areas": [
            {
                "title": "Customer queries",
                "detail": "The notebook demonstrates filtering customers by state, including customers from Kerala.",
            },
            {
                "title": "Revenue and orders",
                "detail": "Example questions include ranking customers by revenue and listing pending orders.",
            },
            {
                "title": "Product purchases",
                "detail": "The notebook demonstrates finding customers who purchased a named product.",
            },
            {
                "title": "Automatic visualization",
                "detail": "The notebook uses Plotly: line charts for date-like columns and bar charts for category/value results.",
            },
        ],
        "limitations": [
            "The notebook contains example query workflows, not a separate precomputed analytics dataset.",
            "Its automatic charting expects the query result to include columns that can be used as categories and numeric measures.",
        ],
    }


@app.get("/api/schema")
async def schema():
    return {"schema": get_schema_context()}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    question = (request.question or "").strip()
    if not question:
        return {"success": False, "message": "Please enter a question before sending."}

    try:
        return execute_question(question)
    except (RuntimeError, ValueError) as exc:
        return {"success": False, "message": str(exc)}


@app.get("/health")
async def health():
    return {"status": "ok"}
