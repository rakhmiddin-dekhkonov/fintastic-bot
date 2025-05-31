from neo4j import GraphDatabase
import json
import re

# Neo4j credentials
uri = "bolt://localhost:7687"
user = "neo4j"
password = "testing123"

driver = GraphDatabase.driver(uri, auth=(user, password))

# Normalize values: "$1,234", "24%" => 1234, 24
def clean_value(val):
    if not isinstance(val, str):
        return val
    val = val.strip()
    val = val.replace(",", "")
    if val.startswith("$"):
        return float(val[1:]) if val[1:].replace(".", "", 1).isdigit() else val
    if val.endswith("%"):
        return float(val[:-1]) if val[:-1].replace(".", "", 1).isdigit() else val
    try:
        return float(val)
    except ValueError:
        return val

# Insert graph structure
def insert_graph(tx, year, metric_name, value):
    tx.run("""
        MERGE (y:Year {value: $year})
        MERGE (m:Metric {name: $metric_name})
        MERGE (v:Value {amount: $value})
        MERGE (y)-[:HAS_METRIC]->(m)
        MERGE (m)-[:HAS_VALUE]->(v)
    """, year=year, metric_name=metric_name, value=value)

# Load JSON
with open("data.json", "r") as f:
    data = json.load(f)

with driver.session() as session:
    for tab in data:
        for key, rows in tab.items():
            if not rows or len(rows) < 2:
                continue
            headers = rows[0]
            for row in rows[1:]:
                year = row[0]
                if not re.match(r"\d{4}", str(year)):
                    continue  # Skip non-year rows
                for i in range(1, len(headers)):
                    metric_name = headers[i].strip()
                    value_raw = row[i] if i < len(row) else None
                    value = clean_value(value_raw)
                    if metric_name and isinstance(value, (int, float)):
                        session.execute_write(insert_graph, year, metric_name, value)

driver.close()
