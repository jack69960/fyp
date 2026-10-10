import json
from pathlib import Path
from neo4j import GraphDatabase

# ==================== Configuration ====================
NEO4J_URI = "neo4j+ssc://7428d6cf.databases.neo4j.io"
NEO4J_USER = "7428d6cf"
NEO4J_PASSWORD = "uXchE9iGSJWZ8gCtJnHMiyGF4Wbbpyfpm3MCdBuBXBU"
NEO4J_DATABASE = "7428d6cf"

CLEAR_DATABASE = True    # Set to True once to wipe and reimport
BATCH_SIZE = 100
NULL_TOKENS = {"N/A", "NA", "NONE", "NULL", "-", ""}
# ========================================================

# Auto-detect the latest triples file (ignore any unmapped leftovers)
DATA_DIR = Path("data/extracted")
candidates = [f for f in DATA_DIR.glob("triples_*.json") if "unmapped" not in f.name]
if not candidates:
    raise FileNotFoundError(f"No triples file found in {DATA_DIR}")

TRIPLES_FILE = sorted(candidates)[-1]
print(f"Auto-loaded latest triples file: {TRIPLES_FILE}")


# ---------- Helper functions ----------
def clean_dataset(value):
    """Return a stripped string, or None if the value is a placeholder."""
    if not value or str(value).strip().upper() in NULL_TOKENS:
        return None
    return str(value).strip()


def clean_triple(t):
    """Convert a raw triple dict into a normalized dict ready for Neo4j.
    Task is kept as-is (NO normalization)."""
    return {
        "method": t["method"].strip(),
        "task": t["task"].strip(),
        "dataset": clean_dataset(t.get("dataset")),
        "confidence": t.get("confidence", 0.8),
        "arxiv_id": t.get("arxiv_id", "unknown"),
        "title": t.get("title", ""),
        "topic": t.get("topic", "unknown"),
    }


# ---------- Neo4j Importer ----------
class Neo4jImporter:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def run(self, triples):
        with self.driver.session(database=NEO4J_DATABASE) as session:
            if CLEAR_DATABASE:
                session.run("MATCH (n) DETACH DELETE n")
                print("[Done] Database cleared")
            else:
                print("[Skip] Clearing database disabled")

            for label in ("Method", "Task", "Dataset"):
                session.run(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.name IS UNIQUE")
            session.run("CREATE CONSTRAINT IF NOT EXISTS FOR (p:Paper) REQUIRE p.arxiv_id IS UNIQUE")
            print("Constraints created")

            query = """
            UNWIND $batch AS t
            MERGE (p:Paper {arxiv_id: t.arxiv_id})
                ON CREATE SET p.title = t.title, p.topic = t.topic
            MERGE (m:Method {name: t.method})
            MERGE (task:Task {name: t.task})
            MERGE (p)-[:PROPOSES]->(m)
            MERGE (p)-[:ADDRESSES]->(task)
            MERGE (m)-[r1:USED_FOR]->(task)
                SET r1.confidence = t.confidence
            FOREACH (ignore IN CASE WHEN t.dataset IS NOT NULL THEN [1] ELSE [] END |
                MERGE (d:Dataset {name: t.dataset})
                MERGE (m)-[r2:EVALUATED_ON]->(d)
                    SET r2.confidence = t.confidence
                MERGE (p)-[:USES]->(d)
            )
            """
            total = len(triples)
            for i in range(0, total, BATCH_SIZE):
                session.run(query, batch=triples[i:i + BATCH_SIZE])
                print(f"  Written {min(i + BATCH_SIZE, total)} / {total}")

        print(f"[Done] Imported {total} triples")


# ---------- Main ----------
def main():
    with open(TRIPLES_FILE, "r", encoding="utf-8") as f:
        raw_triples = json.load(f)

    print(f"Loaded {len(raw_triples)} raw triples")

    # Only filter empty method/task; keep everything else as-is
    cleaned = [clean_triple(t) for t in raw_triples if t.get("method") and t.get("task")]
    print(f"After cleaning: {len(cleaned)} valid triples")

    importer = Neo4jImporter()
    try:
        importer.run(cleaned)
        print("\n[Done] Import complete! Open Neo4j Aura Console -> Query or Bloom.")
    finally:
        importer.close()


if __name__ == "__main__":
    main()