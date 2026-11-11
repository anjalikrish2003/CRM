# CRM AI Analytics

A conversational analytics web app for the CRM database. Ask questions in natural language and view database-backed answers as summaries, tables, and charts.

## Features

- Natural-language questions about customers, products, orders, leads, and employees
- Read-only SQL generation using the database schema
- Tabular query results and automatic visualizations
- Dataset information, including tables, columns, record counts, missing values, and relationships
- Notebook workflow and analysis examples from `crm.ipynb`
- Chat history saved locally in the current browser

## Requirements

- Python 3.10 or later
- An API key for Groq or Google Gemini

The app uses Groq by default and Gemini as a fallback when both API keys are configured. API keys are read by the backend from `.env`; do not put keys in frontend files or commit them to GitHub.

## Setup on Windows

Open PowerShell in the project directory:

```powershell
cd D:\GenAI\CRM
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root and add at least one provider key:

```dotenv
GROQ_API_KEY=your_groq_api_key
```

Or configure Gemini instead:

```dotenv
GEMINI_API_KEY=your_gemini_api_key
```

To use Groq as the primary provider and Gemini as a fallback, configure both keys. The model names can optionally be changed with `GROQ_MODEL` and `GEMINI_MODEL`; defaults are `openai/gpt-oss-120b` and `gemini-3.6-flash`.

## Run the application

From the project directory:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Keep the terminal open while using the app. Visit <http://127.0.0.1:8000/> in your browser. Stop the server with **Ctrl+C**.

On first startup, the app creates a local SQLite database named `crm.db` from `crm.sql`. The generated database is ignored by Git; the SQL source file is tracked with the project.

## Example questions

- How many customers are there?
- Show pending orders.
- Which product has the highest price?
- What is the average order value?
- How many leads are in each status?
- What is the total revenue by state?

Questions must be answerable using the tables and columns in the CRM database. Database queries are restricted to read-only SQL.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/` | Web application |
| `GET` | `/health` | Server health check |
| `GET` | `/api/dataset` | Database tables, columns, counts, and relationships |
| `GET` | `/api/schema` | Database schema context |
| `GET` | `/api/sample-questions` | Suggested questions |
| `GET` | `/api/notebook-insights` | Notebook workflow and analysis overview |
| `POST` | `/api/chat` | Answer a question; JSON body: `{"question":"..."}` |

Interactive API documentation is available at <http://127.0.0.1:8000/docs> while the server is running.

## Project structure

```text
backend/       FastAPI app, query engine, and database helpers
static/        Frontend JavaScript and CSS
templates/     HTML page template
crm.sql        CRM schema and seed data
crm.ipynb      Gemini-based CRM analytics notebook
crm_groq.ipynb Groq-based CRM analytics notebook
requirements.txt
```

## Troubleshooting

- **Chat reports missing API configuration:** Create `.env` in the project root and set `GROQ_API_KEY` or `GEMINI_API_KEY`, then restart the server.
- **Changes do not appear in the browser:** Refresh the page. Restart Uvicorn after backend changes.
- **Port 8000 is already in use:** Stop the other server process or run Uvicorn on another port, for example `--port 8001`.
- **Resetting local data:** Stop the server, remove the generated `crm.db`, and start the app again to recreate it from `crm.sql`.
