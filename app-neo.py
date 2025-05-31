import streamlit as st
import requests
from neo4j import GraphDatabase
import re

# ---- CONFIG ----
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "testing123"
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:latest"

# ---- INIT ----
st.set_page_config(page_title="FIN-Bot (Neo4j)", layout="centered")
st.title("FIN-Bot with Neo4j Reasoning")

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- NEO4J SETUP ----
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

# ---- SYMBOLIC ANALYSIS ----
def run_symbolic_analysis(prompt):
    match = re.search(r"percentage change in (.*?) from (\d{4}) to (\d{4})", prompt.lower())
    if not match:
        return None, None

    metric_keyword, year1, year2 = match.groups()
    metric_keyword = metric_keyword.strip()

    with driver.session() as session:
        query = f"""
        MATCH (y:Year)-[:HAS_METRIC]->(m)-[:HAS_VALUE]->(v)
        WHERE toLower(m.name) CONTAINS $metric AND y.value IN [$year1, $year2]
        RETURN y.value AS year, m.name AS metric, v.amount AS value
        """
        records = session.run(query, metric=metric_keyword, year1=year1, year2=year2)
        values = {r["year"]: r["value"] for r in records}

    if year1 not in values or year2 not in values:
        return "❌ Required data not found in graph.", ""

    val1 = values[year1]
    val2 = values[year2]
    try:
        change = ((val2 - val1) / val1) * 100
        explanation = f"{metric_keyword.title()} in {year1} = {val1}\n{metric_keyword.title()} in {year2} = {val2}\nPercent Change = (({val2} - {val1}) / {val1}) * 100 = {change:.2f}%"
        graph_data = f"[{year1}] {metric_keyword.title()} → {val1}\n[{year2}] {metric_keyword.title()} → {val2}"
        return explanation, graph_data
    except ZeroDivisionError:
        return "❌ Cannot compute percentage change due to division by zero.", ""

# ---- DEFAULT SUBGRAPH RETRIEVAL ----
def get_relevant_subgraph(prompt: str) -> str:
    with driver.session() as session:
        candidate_years = re.findall(r"\b(20\d{2})\b", prompt)
        detected_metrics = []
        metric_keywords = ["fuel", "expense", "revenue", "utilization", "cost", "income", "price", "load", "gallons"]
        for word in metric_keywords:
            if word in prompt.lower():
                detected_metrics.append(word)

        db_years = session.run("MATCH (y:Year) RETURN y.value AS year")
        valid_years = {record["year"] for record in db_years}
        years = [y for y in candidate_years if y in valid_years]

        where_clauses = []
        if years:
            where_clauses += [f'y.value = "{y}"' for y in years]
        if detected_metrics:
            where_clauses += [f'toLower(m.name) CONTAINS "{k}"' for k in detected_metrics]
        where_clause = "TRUE" if not where_clauses else " OR ".join(where_clauses)

        query = f"""
        MATCH (y:Year)-[:HAS_METRIC]->(m)-[:HAS_VALUE]->(v)
        WHERE {where_clause}
        RETURN y.value AS year, labels(m)[0] AS type, m.name AS metric, v.amount AS value
        ORDER BY year, metric
        LIMIT 100
        """

        records = session.run(query)
        lines = []
        for r in records:
            lines.append(f"[{r['year']}] {r['type']} | {r['metric']} → {r['value']}")
        return "\n".join(lines) if lines else "⚠️ No relevant data was found for the question."

# ---- DISPLAY CHAT HISTORY ----
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["text"])

# ---- USER PROMPT ----
prompt = st.chat_input("Ask a question about financial performance...")

# ---- CHAT INFERENCE ----
if prompt:
    st.session_state.messages.append({"role": "user", "text": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        with st.spinner("Analyzing graph and performing reasoning..."):
            symbolic_explanation, graph_data = run_symbolic_analysis(prompt)
            if symbolic_explanation:
                context_data = f"{graph_data}\n\n### Computation:\n{symbolic_explanation}"
            else:
                context_data = get_relevant_subgraph(prompt)

        full_prompt = f"""
You are a financial analyst AI assistant. Use the graph-based data and symbolic computations below to answer the user's question.

### Graph Data:
{context_data}

### Question:
{prompt}

### Answer:
"""

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
