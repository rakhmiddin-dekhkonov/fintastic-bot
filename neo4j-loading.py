from neo4j import GraphDatabase
import json

# Neo4j credentials
uri = "bolt://localhost:7687"
user = "neo4j"
password = "testing123"

driver = GraphDatabase.driver(uri, auth=(user, password))

def insert_metrics(tx, year, metrics):
    tx.run("MERGE (y:Year {value: $year})", year=year)
    for name, value in metrics.items():
        tx.run("""
            MERGE (m:Metric {name: $name, value: $value})
            MERGE (y:Year {value: $year})-[:HAS_METRIC]->(m)
        """, name=name, value=value, year=year)

with open("data.json", "r") as f:
    data = json.load(f)

with driver.session() as session:
    for tab in data:
        for key, rows in tab.items():
            header = rows[0]
            for row in rows[1:]:
                year = row[0]
                metrics = {header[i]: row[i] for i in range(1, len(row))}
                session.execute_write(insert_metrics, year, metrics)

driver.close()
