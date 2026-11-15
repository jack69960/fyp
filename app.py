import streamlit as st
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import pandas as pd
import tempfile
import os

# ==================== Configuration ====================
# The data source is chosen automatically, in this order:
#   1) st.secrets["neo4j"] on Streamlit Cloud (connects to an Aura instance)
#   2) .env / environment variables (defaults to a local Neo4j Community server)
#   3) if the database is unreachable, fall back to the data/graph_export.json
#      snapshot, so the cloud deployment runs without any database at all.
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _secrets_neo4j():
    """Read Streamlit Cloud secrets; return None when running locally."""
    try:
        sec = st.secrets["neo4j"]
        if sec.get("uri") and sec.get("password"):
            return {
                "uri": sec["uri"],
                "user": sec.get("username", "neo4j"),
                "password": sec["password"],
                "database": sec.get("database", "neo4j"),
            }
    except Exception:
        pass
    return None


_SECRETS = _secrets_neo4j()

NEO4J_URI = _SECRETS["uri"] if _SECRETS else os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = _SECRETS["user"] if _SECRETS else os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = _SECRETS["password"] if _SECRETS else os.getenv("NEO4J_PASSWORD", "fyp-neo4j-2026")
NEO4J_DATABASE = _SECRETS["database"] if _SECRETS else os.getenv("NEO4J_DATABASE", "neo4j")

DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "graph_export.json")
# Force the snapshot for testing: FYP_FORCE_JSON=1
FORCE_JSON = os.getenv("FYP_FORCE_JSON", "").lower() in {"1", "true", "yes"}

NODE_COLORS = {
    "Paper":  "#4C9BE8",   # blue
    "Method": "#7ED957",   # green
    "Task":   "#F4D03F",   # yellow
    "Dataset":"#E85C4C",   # red
}

# Node sizes: Task largest (visual anchor), Method medium, Paper/Dataset small
NODE_SIZES = {
    "Task":   32,
    "Method": 20,
    "Paper":  12,
    "Dataset":12,
}

# Task categories (only used to group rows in the research-gap tab)
TASK_CATEGORIES = {
    "Math Reasoning": ["math", "arithmetic", "geometric", "theorem", "equation"],
    "Code Generation": ["code", "program", "software", "compilation"],
    "Language Modeling": ["language model", "text generation", "pretraining", "token"],
    "Agents": ["agent", "planning", "decision", "multi-agent"],
    "Multimodal": ["vision", "visual", "image", "video", "audio", "multimodal", "vlm"],
    "Retrieval": ["retrieval", "rag", "search", "knowledge base"],
    "Alignment & RLHF": ["alignment", "rlhf", "preference", "reward", "human feedback"],
    "Distillation": ["distill", "knowledge transfer", "compression", "teacher"],
    "Efficient Inference": ["quantization", "pruning", "efficient", "sparsity", "acceleration"],
    "Long Context": ["long context", "long-context", "context extension"],
    "Test-Time Compute": ["test-time", "test time", "inference-time", "scaling"],
    "Safety & Evaluation": ["safety", "jailbreak", "robustness", "evaluation", "benchmark"],
}
# ========================================================


@st.cache_resource(show_spinner=False)
def get_driver():
    """Return a driver when the database is reachable, else None (snapshot mode)."""
    if FORCE_JSON:
        return None
    try:
        driver = GraphDatabase.driver(
            NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD), connection_timeout=3
        )
        driver.verify_connectivity()
        return driver
    except Exception:
        return None


_DRIVER = get_driver()
USE_JSON = _DRIVER is None


@st.cache_resource(show_spinner=False)
def get_store():
    """Snapshot data source (only used when the database is unreachable)."""
    from graph_json import GraphStore

    return GraphStore(DATA_FILE, node_to_dict)


@st.cache_data(ttl=600, show_spinner=False)
def run_query(query, **params):
    with _DRIVER.session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(query, **params)]


def categorize_task(task_name: str) -> str:
    t = task_name.lower()
    for category, keywords in TASK_CATEGORIES.items():
        for kw in keywords:
            if kw in t:
                return category
    return "Other"


# ==================== Node/Edge helpers ====================
def node_to_dict(node, label_type):
    """Turn a graph node into the structure pyvis expects."""
    if label_type == "Paper":
        raw = node.get("title") or "Untitled"
        label = raw[:28] + ("..." if len(raw) > 28 else "")
        title = f"Paper: {raw}\nTopic: {node.get('topic','')}"
    else:
        raw = node.get("name") or "?"
        label = raw[:28] + ("..." if len(raw) > 28 else "")
        title = f"{label_type}: {raw}"
    return {"label": label, "type": label_type, "title": title}


# ==================== Data fetchers ====================
def get_all_topics():
    if USE_JSON:
        return get_store().topics()
    rows = run_query("MATCH (p:Paper) RETURN DISTINCT p.topic AS topic ORDER BY topic")
    return [r["topic"] for r in rows if r["topic"]]


def get_all_tasks():
    """Return tasks ordered by number of associated methods (most studied first)."""
    if USE_JSON:
        return get_store().tasks()
    query = """
    MATCH (t:Task)<-[:USED_FOR]-(m:Method)
    WITH t, count(DISTINCT m) AS method_count
    RETURN t.name AS task, method_count
    ORDER BY method_count DESC, task
    """
    return run_query(query)


def fetch_by_topic(topic, limit=80):
    """Topic mode: subgraph centred on Paper nodes. Returns (nodes, edges)."""
    if USE_JSON:
        return get_store().topic_subgraph(topic, limit)
    query = """
    MATCH (p:Paper)-[r]-(n)
    WHERE p.topic = $topic
    RETURN p, r, n
    LIMIT $limit
    """
    with get_driver().session(database=NEO4J_DATABASE) as session:
        records = list(session.run(query, topic=topic, limit=limit))

    nodes, edges = {}, []
    for rec in records:
        p, r, n = rec["p"], rec["r"], rec["n"]
        if p is None or n is None:
            continue
        pid = f"Paper_{p.element_id}"
        n_type = list(n.labels)[0]
        nid = f"{n_type}_{n.element_id}"

        if pid not in nodes:
            nodes[pid] = node_to_dict(p, "Paper")
        if nid not in nodes:
            nodes[nid] = node_to_dict(n, n_type)

        # Orient the edge away from the Paper node.
        if r.start_node.element_id == p.element_id:
            edges.append((pid, nid, r.type))
        else:
            edges.append((nid, pid, r.type))
    return nodes, edges


def fetch_by_tasks(task_names, max_methods=25):
    """
    Task mode: subgraph radiating from Task nodes.
    Shape: Task <- USED_FOR - Method <- PROPOSES - Paper
                           Method - EVALUATED_ON -> Dataset
    Tasks sharing a method are connected automatically.
    """
    if USE_JSON:
        return get_store().tasks_subgraph(task_names, max_methods)
    query = """
    MATCH (t:Task)<-[:USED_FOR]-(m:Method)
    WHERE t.name IN $tasks
    WITH t, m
    LIMIT $limit
    OPTIONAL MATCH (p:Paper)-[:PROPOSES]->(m)
    OPTIONAL MATCH (m)-[:EVALUATED_ON]->(d:Dataset)
    RETURN t, m, p, d
    """
    limit = max_methods * len(task_names) * 3
    with get_driver().session(database=NEO4J_DATABASE) as session:
        records = list(session.run(query, tasks=list(task_names), limit=limit))

    nodes, edges = {}, []
    seen_edges = set()

    def add_edge(src, dst, rel):
        key = (src, dst, rel)
        if key not in seen_edges:
            seen_edges.add(key)
            edges.append(key)

    for rec in records:
        t, m, p, d = rec["t"], rec["m"], rec["p"], rec["d"]
        tid = mid = pid = did = None

        if t is not None:
            tid = f"Task_{t.element_id}"
            if tid not in nodes:
                nodes[tid] = node_to_dict(t, "Task")
        if m is not None:
            mid = f"Method_{m.element_id}"
            if mid not in nodes:
                nodes[mid] = node_to_dict(m, "Method")
            if tid:
                add_edge(tid, mid, "USED_FOR")
        if p is not None and mid:
            pid = f"Paper_{p.element_id}"
            if pid not in nodes:
                nodes[pid] = node_to_dict(p, "Paper")
            add_edge(pid, mid, "PROPOSES")
        if d is not None and mid:
            did = f"Dataset_{d.element_id}"
            if did not in nodes:
                nodes[did] = node_to_dict(d, "Dataset")
            add_edge(mid, did, "EVALUATED_ON")

    return nodes, edges


# ==================== Pyvis rendering ====================
def build_pyvis(nodes, edges):
    net = Network(height="700px", width="100%", directed=True,
                  bgcolor="#1e1e1e", font_color="white", notebook=False)

    # Inject native vis.js options, bypassing pyvis defaults
    net.set_options("""
    var options = {
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -5000,
          "centralGravity": 0.35,
          "springLength": 130,
          "springConstant": 0.04,
          "damping": 0.2,
          "avoidOverlap": 0.3
        },
        "stabilization": {
          "enabled": true,
          "iterations": 300,
          "updateInterval": 25,
          "fit": true
        }
      },
      "edges": {
        "color": {"color": "rgba(170, 170, 170, 0.85)", "highlight": "#FFFFFF"},
        "width": 1.5,
        "smooth": false,
        "arrows": {"to": {"enabled": true, "scaleFactor": 0.5}}
      },
      "nodes": {
        "font": {"color": "#FFFFFF", "size": 14, "strokeWidth": 2, "strokeColor": "#000000"},
        "borderWidth": 0
      },
      "interaction": {"hover": true, "tooltipDelay": 100}
    }
    """)

    for nid, info in nodes.items():
        net.add_node(
            nid,
            label=info["label"],
            title=info["title"],
            color=NODE_COLORS.get(info["type"], "#999999"),
            size=NODE_SIZES.get(info["type"], 12),
            # Give Task nodes more mass so they settle at the centre
            mass=3 if info["type"] == "Task" else 1
        )

    for src, dst, rel in edges:
        # Use title (hover tooltip) rather than label, which would cover the line
        net.add_edge(src, dst, title=rel)

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8")
    net.save_graph(tmp.name)
    return tmp.name


# ==================== Research Gap Queries ====================
@st.cache_data(ttl=60)
def find_rare_tasks(min_methods, min_papers=2, min_name_len=6):
    query = """
    MATCH (t:Task)<-[:USED_FOR]-(m:Method)
    OPTIONAL MATCH (t)<-[:ADDRESSES]-(p:Paper)
    WITH t, count(DISTINCT m) AS method_count, count(DISTINCT p) AS paper_count
    WHERE method_count <= $min_methods
      AND paper_count >= $min_papers
      AND size(t.name) >= $min_name_len
    RETURN t.name AS task, method_count, paper_count
    ORDER BY method_count ASC, paper_count DESC, task
    """
    if USE_JSON:
        rows = get_store().rare_tasks(min_methods, min_papers, min_name_len)
    else:
        rows = run_query(query, min_methods=min_methods,
                         min_papers=min_papers, min_name_len=min_name_len)
    for r in rows:
        r["category"] = categorize_task(r["task"])
    return rows


@st.cache_data(ttl=60)
def find_unevaluated_methods(min_papers=1):
    query = """
    MATCH (m:Method)
    WHERE NOT (m)-[:EVALUATED_ON]->(:Dataset)
    OPTIONAL MATCH (p:Paper)-[:PROPOSES]->(m)
    WITH m, count(DISTINCT p) AS paper_count
    WHERE paper_count >= $min_papers
    RETURN m.name AS method, paper_count
    ORDER BY paper_count DESC, method
    """
    if USE_JSON:
        return get_store().unevaluated_methods(min_papers)
    return run_query(query, min_papers=min_papers)


@st.cache_data(ttl=60)
def find_orphan_methods():
    query = """
    MATCH (p:Paper)-[:PROPOSES]->(m:Method)
    WITH m, count(DISTINCT p) AS paper_count
    WHERE paper_count = 1
    OPTIONAL MATCH (m)-[:USED_FOR]->(t:Task)
    RETURN m.name AS method, collect(DISTINCT t.name) AS related_tasks
    ORDER BY method
    """
    if USE_JSON:
        return get_store().orphan_methods()
    return run_query(query)


@st.cache_data(ttl=60)
def find_cross_topic_methods():
    query = """
    MATCH (p:Paper)-[:PROPOSES]->(m:Method)
    WITH m, collect(DISTINCT p.topic) AS topics
    WHERE size(topics) > 1
    RETURN m.name AS method, topics
    ORDER BY size(topics) DESC
    """
    if USE_JSON:
        return get_store().cross_topic_methods()
    return run_query(query)


# ==================== Page ====================
st.set_page_config(page_title="Academic Knowledge Graph Explorer", layout="wide")
st.title("🔬 Academic Knowledge Graph Explorer")
st.caption("An interactive research map built from method–task–dataset triples extracted from arXiv papers.")

if USE_JSON and not os.path.exists(DATA_FILE):
    st.error("Could not reach Neo4j and the snapshot data/graph_export.json is missing. "
             "Run `python export_graph_json.py` to generate it.")
    st.stop()

tab_graph, tab_gaps = st.tabs(["🔍 Graph Explorer", "💡 Research Gaps"])

# ---------- Tab 1: Graph Explorer ----------
with tab_graph:
    # --- Sidebar controls ---
    with st.sidebar:
        st.header("🎛️ Controls")
        if USE_JSON:
            st.caption("📦 Data source: bundled snapshot graph_export.json (no database required)")
        else:
            st.caption(f"🗄️ Data source: live Neo4j ({NEO4J_URI})")
        mode = st.radio("Exploration mode", ["By research topic", "By task (recommended)"], index=1)

        if mode == "By research topic":
            topics = get_all_topics()
            if not topics:
                st.warning("No data in the database. Run import_neo4j.py first.")
                st.stop()
            selected_topic = st.selectbox("Research topic", topics)
            limit = st.slider("Max relations to display", 20, 300, 60, 20)

        else:
            tasks = get_all_tasks()
            if not tasks:
                st.warning("No tasks found in the database.")
                st.stop()
            task_options = [t["task"] for t in tasks]
            default_tasks = task_options[:1] if task_options else []
            selected_tasks = st.multiselect(
                "Select tasks (up to 3)",
                options=task_options,
                default=default_tasks,
                help="When several tasks share a method, the graph connects them automatically."
            )
            if len(selected_tasks) > 3:
                selected_tasks = selected_tasks[:3]
                st.info("At most 3 tasks can be shown at once.")

        st.divider()
        st.markdown("**Legend**")
        st.markdown(
            f"- <span style='color:{NODE_COLORS['Task']}'>●</span> Task\n"
            f"- <span style='color:{NODE_COLORS['Method']}'>●</span> Method\n"
            f"- <span style='color:{NODE_COLORS['Paper']}'>●</span> Paper\n"
            f"- <span style='color:{NODE_COLORS['Dataset']}'>●</span> Dataset",
            unsafe_allow_html=True
        )

    # --- Main area ---
    if mode == "By research topic":
        nodes, edges = fetch_by_topic(selected_topic, limit)
        title = f"Research topic: `{selected_topic}` — {len(nodes)} nodes, {len(edges)} relations"
    else:
        if not selected_tasks:
            st.info("Please select at least one task in the sidebar.")
            st.stop()
        nodes, edges = fetch_by_tasks(selected_tasks)
        title = f"Tasks: {', '.join(selected_tasks)} — {len(nodes)} nodes, {len(edges)} relations"

    if not nodes:
        st.info("No subgraph matches the current filters.")
    else:
        st.subheader(title)
        html_path = build_pyvis(nodes, edges)
        with open(html_path, "r", encoding="utf-8") as f:
            graph_html = f.read()
        if hasattr(st, "iframe"):  # Streamlit >= 1.6x: components.html is deprecated
            st.iframe(graph_html, width="stretch", height=720, alt="Knowledge graph (drag to pan, scroll to zoom)")
        else:
            components.html(graph_html, height=720, scrolling=True)
        os.unlink(html_path)

# ---------- Tab 2: Research Gaps ----------
with tab_gaps:
    st.header("💡 Potential Research Gaps")
    st.caption("Heuristic suggestions derived from the knowledge graph. Treat them as leads, not "
               "conclusions — verify each one by reading the underlying papers.")

    st.subheader("1. Rare tasks (few associated methods)")
    st.markdown(
        "Tasks with only a handful of associated methods may be under-explored. "
        "Tasks mentioned by very few papers are filtered out as noise."
    )
    col_a, col_b = st.columns(2)
    with col_a:
        min_methods = st.slider("Max methods per task", 1, 5, 2)
    with col_b:
        min_papers = st.slider("Min papers mentioning the task", 1, 5, 2)

    rare_tasks = find_rare_tasks(min_methods, min_papers=min_papers)
    if rare_tasks:
        df = pd.DataFrame(rare_tasks).rename(columns={
            "category": "Category", "task": "Task",
            "method_count": "# Methods", "paper_count": "# Papers",
        })
        categories = ["All"] + sorted(df["Category"].unique().tolist())
        selected_cat = st.selectbox("Filter by category", categories)
        if selected_cat != "All":
            df = df[df["Category"] == selected_cat]
        st.dataframe(
            df[["Category", "Task", "# Methods", "# Papers"]],
            width="stretch", hide_index=True
        )
        st.caption(f"Showing {len(df)} row(s)")
    else:
        st.info("No rare tasks at the current thresholds.")

    st.divider()

    st.subheader("2. Methods never evaluated on a dataset")
    st.markdown("Methods with no EVALUATED_ON edge to any dataset may lack a standardised benchmark.")
    unevaluated = find_unevaluated_methods()
    if unevaluated:
        df = pd.DataFrame(unevaluated).rename(columns={
            "method": "Method", "paper_count": "# Papers",
        })
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("Every method is linked to at least one dataset.")

    st.divider()

    st.subheader("3. Orphan methods (proposed by a single paper)")
    st.markdown("Methods introduced by only one paper: possibly an emerging direction, possibly "
                "work that has not been followed up yet.")
    orphans = find_orphan_methods()
    if orphans:
        df = pd.DataFrame(orphans).rename(columns={
            "method": "Method", "related_tasks": "Related tasks",
        })
        df["Related tasks"] = df["Related tasks"].apply(
            lambda x: ", ".join(sorted(x)) if x else "—"
        )
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No orphan methods found.")

    st.divider()

    st.subheader("4. Cross-topic methods")
    st.markdown("Methods appearing in more than one research topic may have cross-domain transfer potential.")
    cross = find_cross_topic_methods()
    if cross:
        df = pd.DataFrame(cross).rename(columns={
            "method": "Method", "topics": "Topics",
        })
        df["Topics"] = df["Topics"].apply(lambda x: ", ".join(sorted(x)))
        st.dataframe(df, width="stretch", hide_index=True)
    else:
        st.info("No cross-topic methods found.")
