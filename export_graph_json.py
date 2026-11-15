"""
把本机 Neo4j 里的知识图谱导出成一份 JSON，供 Streamlit Cloud 版直接读取（不依赖数据库）。

用法：
    .\\.venv\\Scripts\\python.exe export_graph_json.py

输出：data/graph_export.json

结构：
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
    print(f"导出完成：{OUT_PATH}")
    print(f"节点 {len(nodes)} 个，关系 {len(rels)} 条，文件 {size_mb:.2f} MB")


if __name__ == "__main__":
    main()
