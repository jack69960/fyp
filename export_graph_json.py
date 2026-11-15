"""
Export the knowledge graph from the local Neo4j instance to a JSON file, so the
Streamlit Cloud deployment can read it directly without any database.

Usage:
    .\\.venv\\Scripts\\python.exe export_graph_json.py

Output: data/graph_export.json

Structure:
{
  "nodes": [{"id": "4:abc:123", "label": "Paper", "props": {...}}, ...],
  "rels":  [{"start": "...", "end": "...", "type": "PROPOSES", "props": {...}}, ...]
}
"""

import json
import os

from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
USER = os.getenv("NEO4J_USER", "neo4j")
PASSWORD = os.getenv("NEO4J_PASSWORD", "fyp-neo4j-2026")
DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "graph_export.json")

NODE_QUERY = """
MATCH (n)
RETURN elementId(n) AS id, labels(n) AS labels, properties(n) AS props
"""

REL_QUERY = """
MATCH (a)-[r]->(b)
RETURN elementId(a) AS start, elementId(b) AS end, type(r) AS type, properties(r) AS props
"""


def main():
    driver = GraphDatabase.driver(URI, auth=(USER, PASSWORD))
    with driver.session(database=DATABASE) as session:
        nodes = [
            {"id": r["id"], "label": (r["labels"] or ["Node"])[0], "props": r["props"]}
            for r in session.run(NODE_QUERY)
        ]
        rels = [
            {"start": r["start"], "end": r["end"], "type": r["type"], "props": r["props"]}
            for r in session.run(REL_QUERY)
        ]
    driver.close()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"nodes": nodes, "rels": rels}, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = os.path.getsize(OUT_PATH) / 1024 / 1024
    print(f"Export complete: {OUT_PATH}")
    print(f"{len(nodes)} nodes, {len(rels)} relationships, {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
