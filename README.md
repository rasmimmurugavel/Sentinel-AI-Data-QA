# 🛡️ Sentinel: Hybrid AI Data QA & Governed Data Agent
**An open-source reference architecture by Vector Cognitive LLC bridging legacy SQL data governance with modern Generative AI and Agentic workflows.**

---

## 🎯 The Problem
Modern AI pipelines and Data Agents fail silently when enterprise data is technically valid (e.g., `VARCHAR`) but semantically corrupted (e.g., web-scraping artifacts like `NaN%Select Skills` or cross-column contradictions). Furthermore, plugging an AI Data Agent directly into raw tables creates severe **hallucination, data-deletion, and PII-leakage risks**.

## 🏗️ End-to-End Architecture: `Ingest → Govern → Split → Prove → Serve`

```text
[ PART 1: UPSTREAM DATA QA PIPELINE (sentinel_runner.py) ]
  Raw Data (Bronze) ──► Staging (Silver)
                              │
                              ▼
             Master Business Rules Table (rules_config.yaml)
               ├── Layer 1: Great Expectations (Math, PKs, Ranges)
               ├── Layer 2: AI Semantic Gatekeeper (Temp = 0.0, JSON)
               └── Layer 3: Automated PII-Masking Gate (Emails/SSNs)
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
     gold_* tables    quarantine_* tables   sql_audit_log
   (Clean & Masked)   (Human-in-the-Loop)  (Immutable Trail)
            │                 │                 │
            └─────────────────┴─────────────────┘
                              │
                              ▼
[ PART 2: GOVERNED DATA AGENT & MCP LAYER (sentinel_agent.py / sentinel_mcp.py) ]
  Guardrails: Table Whitelist (No Bronze/Silver) | Read-Only SELECT Lock | HITL
  Engine:     DuckDB + Gemini API Model Router (Flash-Lite vs. Flash) + 503 Fallback
  Interfaces: Streamlit Web UI (app.py) & FastMCP Server (Claude / Cursor / Agents)



How It Works (The 4-Word Anchor)
Ingest (Bronze → Silver): Centralizes structured tables and parses unstructured text into conformed silver_ staging tables.
Govern (2-Layer Gatekeeper): Reads a central Master Business Rules Table (rules_config.yaml)—zero hardcoded scripts per table.
Layer 1 (Deterministic): Great Expectations enforces exact math (unique primary keys, null checks, numeric ranges).
Layer 2 (Semantic): A constrained LLM (temperature=0.0) catches unstructured text artifacts (NaN%Select Skills) and cross-column logic anomalies.
Split (Safety & Privacy): Automated regex PII masking scrubs emails and SSNs ([REDACTED_EMAIL]) before AI consumption. Clean rows route to gold_, failing rows isolate into quarantine_ for Human-in-the-Loop (HITL) review, and every decision logs to sql_audit_log.
Prove (Evaluation & Reconciliation):
Row-Count Parity: Asserts Silver == Gold + Quarantine (zero silent data loss).
LLM Evaluation: Runs confusion matrix benchmarks measuring Precision, Recall, and Zero PII Leaks, paired with DeepEval / Ragas offline Faithfulness checks.
Serve (Governed Data Agent & MCP): Exposes only gold_, quarantine_, and sql_audit_log through a read-only DuckDB + Gemini Data Agent (sentinel_agent.py), a Streamlit dashboard (app.py), and a standard FastMCP server (sentinel_mcp.py) with automated model routing and 503 fallback resilience.