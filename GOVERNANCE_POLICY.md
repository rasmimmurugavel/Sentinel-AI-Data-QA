
---

### Step 3: Copy-Paste `GOVERNANCE_POLICY.md`

Create a new file named **`GOVERNANCE_POLICY.md`** at the root of your repo[span_11](start_span)[span_11](end_span). This proves **policy ownership** as an AI Enabler[span_12](start_span)[span_12](end_span)[span_13](start_span)[span_13](end_span):

```markdown
# 📜 Sentinel AI Data Governance & Acceptable Use Policy

**Owner:** Vector Cognitive LLC — AI Governance & Data QA Architecture  
**Scope:** Applies to all Medallion pipelines (`bronze_`, `silver_`, `gold_`, `quarantine_`), LLM Semantic Gatekeepers, Data Agents, and MCP Servers.

---

## 1. Core Governance Principles
1. **Never Use LLMs for Deterministic Math:** Exact counts, primary key uniqueness, null checks, and numeric range bounds must be enforced deterministically by Layer 1 (Great Expectations / SQL).
2. **Pre-Model PII Redaction (Zero Leakage Mandate):** No raw Personally Identifiable Information (emails, SSNs, account numbers) may be sent to external LLM APIs or promoted to `gold_` tables. All text columns must pass through the automated PII-masking gate (`[REDACTED_EMAIL]`, `[REDACTED_SSN]`).
3. **Human-in-the-Loop (HITL) Quarantine:** Automated pipelines and AI Agents are strictly prohibited from deleting or mutating production data. All failing rows must be routed to `quarantine_` tables with `PENDING_APPROVAL` status for human Data Steward sign-off.
4. **Immutable Auditability & Parity:** Every validation check must be logged to `sql_audit_log` with timestamps and failing samples. Every batch must pass Bronze-to-Gold row-count parity (`Silver == Gold + Quarantine`).

## 2. Data Agent & MCP Security Guardrails
All natural-language Data Agents and MCP tool servers (`sentinel_agent.py`, `sentinel_mcp.py`) must enforce:
* **Strict Table Whitelist:** Physical access is restricted solely to `gold_*`, `quarantine_*`, and `sql_audit_log`. Queries referencing `bronze_*` or `silver_*` are automatically blocked at runtime.
* **Read-Only SQL Lock:** Only `SELECT` statements are permitted. Any query containing `DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `CREATE`, or `TRUNCATE` is immediately rejected.
* **Deterministic Grounding:** Agent models operate at `temperature = 0.0` and must ground all answers strictly in SQL tool outputs—never fabricated metrics.
* **Cost & Reliability Governance:** Requests are routed by task complexity (lightweight models for simple lookups, reasoning models for multi-table QA triage) with automatic retry/fallback handling for upstream API outages (`503`).

## 3. Release & Evaluation Gates (SDLC Phase 4)
Before any pipeline or agent rule is promoted to production:
* **Offline Evaluation Benchmark:** Must pass synthetic Golden Dataset testing with **≥ 99% Precision** (low operational friction), **100% Recall** on critical anomalies, and **0 PII Leaks**.
* **Faithfulness Check:** Unstructured AI summaries and RAG responses must be benchmarked via DeepEval/Ragas prior to UAT sign-off.
