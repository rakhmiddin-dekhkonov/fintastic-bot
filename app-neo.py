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
    prompt_lower = prompt.lower()
    years = re.findall(r"\b(20\d{2})\b", prompt)
    if len(years) < 2:
        return "❌ Could not extract two valid years from the question.", ""

    year1, year2 = sorted(years)[:2]
    metric_keywords = ["fuel", "revenue", "cost", "utilization", "income", "expense", "price", "load", "gallons"]

    found_metric = None
    for m in metric_keywords:
        if m in prompt_lower:
            found_metric = m
            break

    if not found_metric:
        return "❌ Could not identify a target metric in the prompt.", ""

    metric_aliases = [
        found_metric,
        f"{found_metric} cost",
        f"{found_metric} expense",
        f"average {found_metric}",
    ]

    with driver.session() as session:
        clauses = " OR ".join([f'toLower(m.name) CONTAINS "{alias}"' for alias in metric_aliases])
        query = f"""
        MATCH (y:Year)-[:HAS_METRIC]->(m)-[:HAS_VALUE]->(v)
        WHERE ({clauses}) AND y.value IN [$year1, $year2]
        RETURN y.value AS year, m.name AS metric, v.amount AS value
        """
        result = session.run(query, year1=year1, year2=year2)
        values = {r["year"]: r["value"] for r in result}

    if year1 not in values or year2 not in values:
        return f"❌ Data missing for years: {year1}, {year2}. Found only: {list(values.keys())}", ""

    try:
        val1 = values[year1]
        val2 = values[year2]
        change = ((val2 - val1) / val1) * 100
        explanation = f"{found_metric.title()} in {year1} = {val1}\n{found_metric.title()} in {year2} = {val2}\nPercent Change = (({val2} - {val1}) / {val1}) * 100 = {change:.2f}%"
        graph_data = f"[{year1}] {found_metric.title()} → {val1}\n[{year2}] {found_metric.title()} → {val2}"
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
