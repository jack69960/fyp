import streamlit as st
from neo4j import GraphDatabase
from pyvis.network import Network
import streamlit.components.v1 as components
import pandas as pd
import tempfile
import os

# ==================== Configuration ====================
NEO4J_URI = "neo4j+ssc://7428d6cf.databases.neo4j.io"
NEO4J_USER = "7428d6cf"
NEO4J_PASSWORD = "uXchE9iGSJWZ8gCtJnHMiyGF4Wbbpyfpm3MCdBuBXBU"
NEO4J_DATABASE = "7428d6cf"

NODE_COLORS = {
    "Paper":  "#4C9BE8",   # 蓝
    "Method": "#7ED957",   # 绿
    "Task":   "#F4D03F",   # 黄
    "Dataset":"#E85C4C",   # 红
}

# 节点大小：Task 最大（视觉中心），Method 中等，Paper/Dataset 小
NODE_SIZES = {
    "Task":   32,
    "Method": 20,
    "Paper":  12,
    "Dataset":12,
}

# Task categorization（只用于"研究空白推荐"里展示分组）
TASK_CATEGORIES = {
    "数学推理": ["math", "arithmetic", "geometric", "theorem", "equation"],
    "代码生成": ["code", "program", "software", "compilation"],
    "语言建模": ["language model", "text generation", "pretraining", "token"],
    "智能体": ["agent", "planning", "decision", "multi-agent"],
    "多模态": ["vision", "visual", "image", "video", "audio", "multimodal", "vlm"],
    "检索增强": ["retrieval", "rag", "search", "knowledge base"],
    "对齐与RLHF": ["alignment", "rlhf", "preference", "reward", "human feedback"],
    "知识蒸馏": ["distill", "knowledge transfer", "compression", "teacher"],
    "高效推理": ["quantization", "pruning", "efficient", "sparsity", "acceleration"],
    "长上下文": ["long context", "long-context", "context extension"],
    "测试时计算": ["test-time", "test time", "inference-time", "scaling"],
    "安全与评估": ["safety", "jailbreak", "robustness", "evaluation", "benchmark"],
}
# ========================================================


@st.cache_resource
def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def run_query(query, **params):
    with get_driver().session(database=NEO4J_DATABASE) as session:
        return [dict(r) for r in session.run(query, **params)]


def categorize_task(task_name: str) -> str:
    t = task_name.lower()
    for category, keywords in TASK_CATEGORIES.items():
        for kw in keywords:
            if kw in t:
                return category
    return "其他"


# ==================== Node/Edge helpers ====================
def node_to_dict(node, label_type):
    """把 Neo4j node 转成 pyvis 需要的结构。"""
    if label_type == "Paper":
        raw = node.get("title") or "无标题"
        label = raw[:28] + ("..." if len(raw) > 28 else "")
        title = f"Paper: {raw}\nTopic: {node.get('topic','')}"
    else:
        raw = node.get("name") or "?"
        label = raw[:28] + ("..." if len(raw) > 28 else "")
        title = f"{label_type}: {raw}"
    return {"label": label, "type": label_type, "title": title}


# ==================== Data fetchers ====================
def get_all_topics():
    rows = run_query("MATCH (p:Paper) RETURN DISTINCT p.topic AS topic ORDER BY topic")
    return [r["topic"] for r in rows if r["topic"]]


def get_all_tasks():
    """返回任务列表，按关联方法数降序（越热门的越靠前）。"""
    query = """
    MATCH (t:Task)<-[:USED_FOR]-(m:Method)
    WITH t, count(DISTINCT m) AS method_count
    RETURN t.name AS task, method_count
    ORDER BY method_count DESC, task
    """
    return run_query(query)


def fetch_by_topic(topic, limit=80):
    """研究方向模式：以 Paper 为中心取子图。返回 (nodes, edges)。"""
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

        # 方向以 Paper 为起点
        if r.start_node.element_id == p.element_id:
            edges.append((pid, nid, r.type))
        else:
            edges.append((nid, pid, r.type))
    return nodes, edges


def fetch_by_tasks(task_names, max_methods=25):
    """
    任务模式：以 Task 为中心辐射。
    结构：Task <- USED_FOR - Method <- PROPOSES - Paper
                            Method - EVALUATED_ON -> Dataset
    多个 Task 共享同一 Method 时会自动连在一起。
    """
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

    # 关键：用 set_options 注入 vis.js 原生配置，避免 pyvis 默认渲染问题
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
            # Task 节点给更大 mass，让它们占据视觉中心
            mass=3 if info["type"] == "Task" else 1
        )

    for src, dst, rel in edges:
        # ⚠️ 用 title（悬停显示）而不是 label（会覆盖边线）
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
    RETURN t.name AS 任务, method_count AS 方法数量, paper_count AS 论文数量
    ORDER BY method_count ASC, paper_count DESC, 任务
    """
    rows = run_query(query, min_methods=min_methods,
                     min_papers=min_papers, min_name_len=min_name_len)
    for r in rows:
        r["类别"] = categorize_task(r["任务"])
    return rows


@st.cache_data(ttl=60)
def find_unevaluated_methods(min_papers=1):
    query = """
    MATCH (m:Method)
    WHERE NOT (m)-[:EVALUATED_ON]->(:Dataset)
    OPTIONAL MATCH (p:Paper)-[:PROPOSES]->(m)
    WITH m, count(DISTINCT p) AS paper_count
    WHERE paper_count >= $min_papers
    RETURN m.name AS 方法, paper_count AS 论文数量
    ORDER BY 论文数量 DESC, 方法
    """
    return run_query(query, min_papers=min_papers)


@st.cache_data(ttl=60)
def find_orphan_methods():
    query = """
    MATCH (p:Paper)-[:PROPOSES]->(m:Method)
    WITH m, count(DISTINCT p) AS paper_count
    WHERE paper_count = 1
    OPTIONAL MATCH (m)-[:USED_FOR]->(t:Task)
    RETURN m.name AS 方法, collect(DISTINCT t.name) AS 相关任务
    ORDER BY 方法
    """
    return run_query(query)


@st.cache_data(ttl=60)
def find_cross_topic_methods():
    query = """
    MATCH (p:Paper)-[:PROPOSES]->(m:Method)
    WITH m, collect(DISTINCT p.topic) AS topics
    WHERE size(topics) > 1
    RETURN m.name AS 方法, topics AS 涉及方向
    ORDER BY size(topics) DESC
    """
    return run_query(query)


# ==================== Page ====================
st.set_page_config(page_title="学术知识图谱探索器", layout="wide")
st.title("🔬 学术知识图谱探索器")
st.caption("从 arXiv 论文中抽取 method–task–dataset 三元组，构建可交互的研究图谱。")

tab_graph, tab_gaps = st.tabs(["🔍 图谱探索", "💡 研究空白推荐"])

# ---------- Tab 1: Graph Explorer ----------
with tab_graph:
    # --- Sidebar controls ---
    with st.sidebar:
        st.header("🎛️ 控制面板")
        mode = st.radio("探索模式", ["按研究方向", "按任务（推荐）"], index=1)

        if mode == "按研究方向":
            topics = get_all_topics()
            if not topics:
                st.warning("数据库中暂无数据，请先运行 import_neo4j.py。")
                st.stop()
            selected_topic = st.selectbox("选择研究方向", topics)
            limit = st.slider("最多显示多少条关系", 20, 300, 60, 20)

        else:
            tasks = get_all_tasks()
            if not tasks:
                st.warning("数据库中没有任务数据。")
                st.stop()
            task_options = [t["task"] for t in tasks]
            default_tasks = task_options[:1] if task_options else []
            selected_tasks = st.multiselect(
                "选择任务（可多选，最多 3 个）",
                options=task_options,
                default=default_tasks,
                help="选多个任务时，共享的方法会自动把它们的图谱连起来。"
            )
            if len(selected_tasks) > 3:
                selected_tasks = selected_tasks[:3]
                st.info("最多同时显示 3 个任务。")

        st.divider()
        st.markdown("**图例**")
        st.markdown(
            f"- <span style='color:{NODE_COLORS['Task']}'>●</span> 任务 Task\n"
            f"- <span style='color:{NODE_COLORS['Method']}'>●</span> 方法 Method\n"
            f"- <span style='color:{NODE_COLORS['Paper']}'>●</span> 论文 Paper\n"
            f"- <span style='color:{NODE_COLORS['Dataset']}'>●</span> 数据集 Dataset",
            unsafe_allow_html=True
        )

    # --- Main area ---
    if mode == "按研究方向":
        nodes, edges = fetch_by_topic(selected_topic, limit)
        title = f"研究方向：`{selected_topic}` —— {len(nodes)} 个节点，{len(edges)} 条关系"
    else:
        if not selected_tasks:
            st.info("请在左侧至少选择一个任务。")
            st.stop()
        nodes, edges = fetch_by_tasks(selected_tasks)
        title = f"任务：{', '.join(selected_tasks)} —— {len(nodes)} 个节点，{len(edges)} 条关系"

    if not nodes:
        st.info("当前条件下没有找到子图数据。")
    else:
        st.subheader(title)
        html_path = build_pyvis(nodes, edges)
        with open(html_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=720, scrolling=True)
        os.unlink(html_path)

# ---------- Tab 2: Research Gaps ----------
with tab_gaps:
    st.header("💡 潜在研究空白推荐")
    st.caption("基于知识图谱的简单启发式规则自动识别，仅供参考，具体结论需阅读论文验证。")

    st.subheader("1. 冷门任务（方法数量少）")
    st.markdown(
        "关联方法数量很少的任务，可能是研究尚未充分覆盖的方向。"
        "已自动过滤只被极少数论文提及的噪音任务。"
    )
    col_a, col_b = st.columns(2)
    with col_a:
        min_methods = st.slider("每个任务最多关联多少个方法", 1, 5, 2)
    with col_b:
        min_papers = st.slider("至少被多少篇论文提及", 1, 5, 2)

    rare_tasks = find_rare_tasks(min_methods, min_papers=min_papers)
    if rare_tasks:
        df = pd.DataFrame(rare_tasks)
        categories = ["全部"] + sorted(df["类别"].unique().tolist())
        selected_cat = st.selectbox("只看某个类别", categories)
        if selected_cat != "全部":
            df = df[df["类别"] == selected_cat]
        st.dataframe(
            df[["类别", "任务", "方法数量", "论文数量"]],
            use_container_width=True, hide_index=True
        )
        st.caption(f"当前显示 {len(df)} 条结果")
    else:
        st.info("在当前阈值下没有发现冷门任务。")

    st.divider()

    st.subheader("2. 未在数据集上评估的方法")
    st.markdown("未连接到任何数据集的 Method，可能缺少标准化基准测试。")
    unevaluated = find_unevaluated_methods()
    if unevaluated:
        st.dataframe(pd.DataFrame(unevaluated), use_container_width=True, hide_index=True)
    else:
        st.info("所有方法都至少连接了一个数据集。")

    st.divider()

    st.subheader("3. 孤立方法（仅 1 篇论文提出）")
    st.markdown("仅被一篇论文提出的方法，可能是新兴方向，也可能是尚未被广泛跟进的工作。")
    orphans = find_orphan_methods()
    if orphans:
        df = pd.DataFrame(orphans)
        df["相关任务"] = df["相关任务"].apply(lambda x: ", ".join(x) if x else "（无）")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("没有发现孤立方法。")

    st.divider()

    st.subheader("4. 跨方向方法")
    st.markdown("出现在多个研究方向中的方法，可能具有跨领域迁移潜力。")
    cross = find_cross_topic_methods()
    if cross:
        df = pd.DataFrame(cross)
        df["涉及方向"] = df["涉及方向"].apply(lambda x: ", ".join(x))
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无跨方向方法。")