import streamlit as st
import requests
from neo4j import GraphDatabase

# ---- CONFIG ----
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testing123"  
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:latest"

# ---- INIT ----
st.set_page_config(page_title="FIN-Bot (Neo4j)", layout="centered")
st.title("FIN-Bot with Neo4j")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- NEO4J SETUP ----
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

def fetch_graph_data(tx):
    result = tx.run("MATCH (y:Year)-[:HAS_METRIC]->(m:Metric) RETURN y.value AS year, m.name AS metric, m.value AS value")
    lines = []
    for record in result:
        lines.append(f"Year: {record['year']} | {record['metric']}: {record['value']}")
    return "\n".join(lines)

# ---- REFRESH DATA ----
if "file_content" not in st.session_state or st.button("🔄 Refresh Financial Data from Neo4j"):
    with driver.session() as session:
        st.session_state.file_content = session.read_transaction(fetch_graph_data)
    st.success("✅ Loaded financial data from Neo4j")

# ---- DISPLAY CHAT HISTORY ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])

# ---- USER PROMPT ----
prompt = st.chat_input("Ask a question about the financial performance...")

# ---- CHAT INFERENCE ----
if prompt:
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    full_prompt = f"""You are an expert financial assistant. Use the following data from a financial knowledge graph to answer the user's question.

### Financial Data:
{st.session_state.file_content[:4000]}  # limited to 4K characters

### Question:
{prompt}

### Answer:
"""

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                res = requests.post(
                    OLLAMA_URL,
                    json={"model": OLLAMA_MODEL, "prompt": full_prompt, "stream": False}
                )
                reply = res.json().get("response", "⚠️ No response from LLaMA.")
            except Exception as e:
                reply = f"❌ Error contacting Ollama backend: {e}"

        st.markdown(reply)
        st.session_state.messages.append({"role": "assistant", "text": reply})
