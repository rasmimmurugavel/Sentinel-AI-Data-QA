import time
import streamlit as st
from google.genai import types
from src.sentinel_agent import (
    client,
    con,
    initialize_demo_tables,
    list_allowed_tables,
    get_table_schema,
    run_readonly_sql,
    choose_gemini_model,
    SYSTEM_PROMPT,
)

st.set_page_config(page_title="Sentinel Governed Data Agent", page_icon="🛡️", layout="wide")
@st.cache_resource
def setup_database():
    initialize_demo_tables()
    return True

setup_database()


st.title("🛡️ Sentinel — Governed AI Data Agent")
st.caption("Read-Only DuckDB + Gemini Model Router | Strict Table Whitelist & HITL Governance")

tab1, tab2 = st.tabs(["💬 Ask Sentinel Agent", "📊 Gold, Quarantine & Audit Log"])

# --- TAB 1: CHAT INTERFACE ---
with tab1:
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("Ask about gold_hr_jobs, quarantine failures, or try a red-team attack..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        primary = choose_gemini_model(prompt)
        fallback = "gemini-3.5-flash-lite" if primary == "gemini-3.8-flash" else "gemini-3.8-flash"

        with st.chat_message("assistant"):
            with st.spinner(f"Routing to `{primary}` and querying DuckDB..."):
                answer = "⚠️ Service temporarily unavailable. Please try again."
                for model_name in [primary, fallback]:
                    try:
                        resp = client.models.generate_content(
                            model=model_name,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                system_instruction=SYSTEM_PROMPT,
                                tools=[list_allowed_tables, get_table_schema, run_readonly_sql],
                                temperature=0.0,
                            ),
                        )
                        answer = f"**Model Used:** `{model_name}`\n\n{resp.text}"
                        break
                    except Exception as e:
                        if "503" in str(e):
                            time.sleep(2)
                        else:
                            answer = f"❌ Error: {e}"
                            break

                st.markdown(answer)
                st.session_state.messages.append({"role": "assistant", "content": answer})

# --- TAB 2: GOVERNANCE & HITL TABLES ---
with tab2:
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("✅ Gold (Clean & PII-Masked)")
        st.dataframe(con.execute("SELECT * FROM gold_hr_jobs;").df(), use_container_width=True)
    with col2:
        st.subheader("⚠️ Quarantine (Pending Human Review)")
        st.dataframe(con.execute("SELECT * FROM quarantine_hr_jobs;").df(), use_container_width=True)

    st.subheader("📜 Immutable SQL Audit Log")
    st.dataframe(con.execute("SELECT * FROM sql_audit_log;").df(), use_container_width=True)
