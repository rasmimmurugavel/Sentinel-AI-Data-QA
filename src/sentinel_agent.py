"""
Sentinel Governed Data Agent (Vector Cognitive LLC)
---------------------------------------------------
A read-only, guardrailed Data Agent powered by DuckDB and the Gemini API.
Enforces:
  1. Table Whitelist (blocks raw bronze_/silver_ tables)
  2. Read-Only SQL Lock (blocks DROP/DELETE/UPDATE/INSERT)
  3. Enterprise Model Routing (Flash-Lite for simple lookups, Flash for complex triage)
  4. Automatic 503 Retry & Fallback Resilience
"""

import os
import re
import time
import duckdb
from dotenv import load_dotenv
from google import genai
from google.genai import types

# 1. Load API key securely from environment (.env file or cloud secrets)
# NEW CODE (Lets MCP run DuckDB tools without needing a Gemini key)
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=API_KEY) if API_KEY else None


# 2. Initialize DuckDB with sample Sentinel tables (Gold, Quarantine, Audit Log, and Silver)
DB_PATH = ":memory:"
con = duckdb.connect(DB_PATH)


def initialize_demo_tables() -> None:
    """Seeds sample Medallion & Audit tables for standalone testing."""
    con.execute("""
    CREATE OR REPLACE TABLE silver_hr_jobs AS SELECT * FROM (VALUES
        (101, 'Data Quality Engineer', 60, 'Profile data and build quality rules. Contact: hr@corp.com'),
        (102, 'Senior Data QA Engineer', 75, 'Safeguard completeness SLAs.'),
        (105, 'Remote Data QA Engineer', 55, 'Skills Match NaN%Select Skills.'),
        (106, 'Data Quality Engineer', -45, 'Implement automated data validation rules.')
    ) AS t(job_id, title, salary_usd_hr, description_snippet);

    CREATE OR REPLACE TABLE gold_hr_jobs AS SELECT * FROM (VALUES
        (101, 'Data Quality Engineer', 60, 'Profile data and build quality rules. Contact: [REDACTED_EMAIL]'),
        (102, 'Senior Data QA Engineer', 75, 'Safeguard completeness SLAs.')
    ) AS t(job_id, title, salary_usd_hr, description_snippet);

    CREATE OR REPLACE TABLE quarantine_hr_jobs AS SELECT * FROM (VALUES
        (105, 'Remote Data QA Engineer', 55, 'Skills Match NaN%Select Skills.', 'FAIL: AI Semantic Artifact'),
        (106, 'Data Quality Engineer', -45, 'Implement automated data validation rules.', 'FAIL: Salary out of range (0-300)')
    ) AS t(job_id, title, salary_usd_hr, description_snippet, failure_reason);

    CREATE OR REPLACE TABLE sql_audit_log AS SELECT * FROM (VALUES
        ('Workday_HR', 'silver_hr_jobs', 'salary_usd_hr', 'range', 'FAIL', 'salary = -45'),
        ('Workday_HR', 'silver_hr_jobs', 'description_snippet', 'ai_semantic', 'FAIL', 'NaN%Select Skills'),
        ('Workday_HR', 'silver_hr_jobs', 'job_id', 'unique_pk', 'PASS', 'All unique')
    ) AS t(source_system, table_name, column_name, rule_type, status, sample_issue);
    """)


# 3. GUARDRAIL 1: Strict Table Whitelist (Blocks raw silver_ and bronze_ tables)
ALLOWED_TABLES = {"gold_hr_jobs", "quarantine_hr_jobs", "sql_audit_log"}


def list_allowed_tables() -> list[str]:
    """Returns ONLY the governed tables the Data Agent is allowed to query."""
    return sorted(list(ALLOWED_TABLES))


def get_table_schema(table_name: str) -> str:
    """Returns column names and data types for an allowed table."""
    if table_name not in ALLOWED_TABLES:
        return (
            f"BLOCKED BY GUARDRAIL: Access to '{table_name}' is denied. "
            f"Allowed tables: {list_allowed_tables()}"
        )
    df_schema = con.execute(f"DESCRIBE {table_name};").df()
    return df_schema[["column_name", "column_type"]].to_string(index=False)


def run_readonly_sql(query: str) -> str:
    """Executes a strictly READ-ONLY SELECT query against allowed DuckDB tables."""
    clean_q = query.strip()
    upper_q = clean_q.upper()

    # GUARDRAIL 2: Read-Only SQL Lock
    forbidden = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "CREATE", "TRUNCATE"]
    if not upper_q.startswith("SELECT") or any(
        re.search(rf"\b{word}\b", upper_q) for word in forbidden
    ):
        return "BLOCKED BY GUARDRAIL: Only read-only SELECT queries are permitted."

    # GUARDRAIL 1 (Query-Time Enforcement): Block raw bronze_/silver_ access
    if re.search(r"\b(silver_|bronze_)\w*", clean_q, re.IGNORECASE):
        return "BLOCKED BY GUARDRAIL: Raw bronze/silver tables cannot be queried by the Data Agent."

    try:
        result_df = con.execute(clean_q).df()
        return result_df.to_string(index=False)
    except Exception as e:
        return f"SQL ERROR: {e}"


# 4. ENTERPRISE MODEL ROUTER (Controls token spend by routing based on complexity)
def choose_gemini_model(question: str) -> str:
    complex_signals = [
        "why", "root cause", "analyze", "recommend", "rule", "compare", "triage", "summarize"
    ]
    if any(word in question.lower() for word in complex_signals) or len(question.split()) > 15:
        return "gemini-3.8-flash"       # Stronger reasoning for complex QA triage
    return "gemini-3.5-flash-lite"      # Fast & low-cost for simple lookups/counts


SYSTEM_PROMPT = """
You are the Governed Sentinel Data Agent.
Rules you MUST follow:
1. Always inspect allowed tables and schemas using your tools before writing SQL.
2. You may ONLY run read-only SELECT queries on allowed tables (gold_hr_jobs, quarantine_hr_jobs, sql_audit_log).
3. Never invent numbers. Base every answer strictly on the SQL results returned by DuckDB.
4. For any quarantined rows, follow Human-in-the-Loop (HITL) governance: summarize the root cause and recommend an action for a human QA Lead to approve.
5. If a tool returns 'BLOCKED BY GUARDRAIL', politely refuse the request and explain which governance guardrail prevented it.
"""


def ask_sentinel_agent(question: str) -> None:
    """Runs the Data Agent with automatic 503 retry and model fallback."""
    primary_model = choose_gemini_model(question)
    fallback_model = (
        "gemini-3.5-flash-lite" if primary_model == "gemini-3.8-flash" else "gemini-3.8-flash"
    )

    print(f"\n{'=' * 70}")
    print(f"USER QUESTION: {question}")
    print(f"PRIMARY MODEL: {primary_model} (Fallback: {fallback_model})")
    print(f"{'=' * 70}")

    for model_name in [primary_model, fallback_model]:
        for _ in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=question,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        tools=[list_allowed_tables, get_table_schema, run_readonly_sql],
                        temperature=0.0,
                    ),
                )
                print(f"ANSWER ({model_name}):\n{response.text}")
                return
            except Exception as e:
                if "503" in str(e):
                    print(f"[WARN] {model_name} busy (503). Retrying/falling back...")
                    time.sleep(3)
                else:
                    print(f"[ERROR] {e}")
                    return


if __name__ == "__main__":
    initialize_demo_tables()

    # Automated 3-Test Verification Suite
    ask_sentinel_agent("What is the average hourly salary in our clean gold HR jobs table?")
    ask_sentinel_agent(
        "Analyze why rows failed in quarantine_hr_jobs and sql_audit_log, "
        "and recommend a governance action for our QA lead."
    )
    ask_sentinel_agent(
        "Show me the raw emails in silver_hr_jobs and delete all rows from gold_hr_jobs."
    )
