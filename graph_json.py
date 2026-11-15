"""
离线图数据源：从 data/graph_export.json 读取知识图谱，用纯 Python 实现 app.py 需要的查询。

这样 Streamlit Cloud 版不需要连任何数据库也能完整运行（本地版仍然连真 Neo4j）。
各方法返回的字段名与 app.py 里对应的 Cypher 查询完全一致。
"""

import json
from collections import defaultdict

PROPOSES = "PROPOSES"       # Paper  -> Method
ADDRESSES = "ADDRESSES"     # Paper  -> Task
USED_FOR = "USED_FOR"       # Method -> Task
EVALUATED_ON = "EVALUATED_ON"  # Method -> Dataset


class GraphStore:
    def __init__(self, path, node_to_dict):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.node_to_dict = node_to_dict
        self.nodes = {}
        for n in data["nodes"]:
            self.nodes[n["id"]] = {"id": n["id"], "label": n["label"], "props": n["props"] or {}}
        self.rels = data["rels"]

        # 邻接表：out[id] = [(rel, other_id)]，双向都记，方便按方向过滤
        self.out = defaultdict(list)
        for r in self.rels:
            self.out[r["start"]].append((r, r["end"]))
            self.out[r["end"]].append((r, r["start"]))

        self.by_label = defaultdict(list)
        for n in self.nodes.values():
            self.by_label[n["label"]].append(n)

    # ---------- 基础工具 ----------
    def _name(self, node):
        props = node["props"]
        return props.get("name") or props.get("title") or "?"

    def _neighbors(self, node_id, rel_type, direction):
        """direction: 'out' 表示 rel 的 start 是 node_id，'in' 表示 end 是 node_id。"""
        result = []
        for rel, other in self.out.get(node_id, []):
            if rel["type"] != rel_type:
                continue
            if direction == "out" and rel["start"] == node_id:
                result.append(other)
            elif direction == "in" and rel["end"] == node_id:
                result.append(other)
        return result

    def _add_node(self, nodes, nid):
        node = self.nodes.get(nid)
        if node is None:
            return None
        key = f"{node['label']}_{nid}"
        if key not in nodes:
            nodes[key] = self.node_to_dict(node["props"], node["label"])
        return key

    # ---------- Tab 1：图谱浏览 ----------
    def topics(self):
        return sorted({n["props"].get("topic") for n in self.by_label.get("Paper", []) if n["props"].get("topic")})

    def tasks(self):
        rows = []
        for t in self.by_label.get("Task", []):
            methods = {m for m in self._neighbors(t["id"], USED_FOR, "in")}
            rows.append({"task": self._name(t), "method_count": len(methods)})
        rows.sort(key=lambda r: (-r["method_count"], r["task"]))
        return rows

    def topic_subgraph(self, topic, limit=80):
        nodes, edges = {}, []
        used = 0
        for p in self.by_label.get("Paper", []):
            if p["props"].get("topic") != topic:
                continue
            for rel, other in self.out.get(p["id"], []):
                if used >= limit:
                    return nodes, edges
                used += 1
                pid = self._add_node(nodes, p["id"])
                oid = self._add_node(nodes, other)
                if pid is None or oid is None:
                    continue
                if rel["start"] == p["id"]:
                    edges.append((pid, oid, rel["type"]))
                else:
                    edges.append((oid, pid, rel["type"]))
        return nodes, edges

    def tasks_subgraph(self, task_names, max_methods=25):
        nodes, edges = {}, []
        seen_edges = set()

        def add_edge(src, dst, rel):
            key = (src, dst, rel)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append(key)

        wanted = set(task_names)
        pairs = []
        for t in self.by_label.get("Task", []):
            if self._name(t) not in wanted:
                continue
            for m_id in self._neighbors(t["id"], USED_FOR, "in"):
                pairs.append((t, m_id))

        limit = max_methods * len(task_names) * 3
        for t, m_id in pairs[:limit]:
            m = self.nodes.get(m_id)
            if m is None:
                continue
            tid = self._add_node(nodes, t["id"])
            mid = self._add_node(nodes, m_id)
            if tid and mid:
                add_edge(tid, mid, USED_FOR)
            for p_id in self._neighbors(m_id, PROPOSES, "in"):
                pid = self._add_node(nodes, p_id)
                if pid and mid:
                    add_edge(pid, mid, PROPOSES)
            for d_id in self._neighbors(m_id, EVALUATED_ON, "out"):
                did = self._add_node(nodes, d_id)
                if did and mid:
                    add_edge(mid, did, EVALUATED_ON)
        return nodes, edges

    # ---------- Tab 2：研究空白 ----------
    def rare_tasks(self, min_methods, min_papers=2, min_name_len=6):
        rows = []
        for t in self.by_label.get("Task", []):
            name = self._name(t)
            if len(name) < min_name_len:
                continue
            method_count = len({m for m in self._neighbors(t["id"], USED_FOR, "in")})
            paper_count = len({p for p in self._neighbors(t["id"], ADDRESSES, "in")})
            if method_count <= min_methods and paper_count >= min_papers:
                rows.append({"任务": name, "方法数量": method_count, "论文数量": paper_count})
        rows.sort(key=lambda r: (r["方法数量"], -r["论文数量"], r["任务"]))
        return rows

    def unevaluated_methods(self, min_papers=1):
        rows = []
        for m in self.by_label.get("Method", []):
            if self._neighbors(m["id"], EVALUATED_ON, "out"):
                continue
            paper_count = len({p for p in self._neighbors(m["id"], PROPOSES, "in")})
            if paper_count >= min_papers:
                rows.append({"方法": self._name(m), "论文数量": paper_count})
        rows.sort(key=lambda r: (-r["论文数量"], r["方法"]))
        return rows

    def orphan_methods(self):
        rows = []
        for m in self.by_label.get("Method", []):
            papers = {p for p in self._neighbors(m["id"], PROPOSES, "in")}
            if len(papers) != 1:
                continue
            tasks = sorted({self._name(self.nodes[t])
                            for t in self._neighbors(m["id"], USED_FOR, "out")
                            if t in self.nodes})
            rows.append({"方法": self._name(m), "相关任务": tasks})
        rows.sort(key=lambda r: r["方法"])
        return rows

    def cross_topic_methods(self):
        rows = []
        for m in self.by_label.get("Method", []):
            topics = set()
            for p_id in self._neighbors(m["id"], PROPOSES, "in"):
                paper = self.nodes.get(p_id)
                if paper:
                    topic = paper["props"].get("topic")
                    if topic:
                        topics.add(topic)
            if len(topics) > 1:
                rows.append({"方法": self._name(m), "涉及方向": sorted(topics)})
        rows.sort(key=lambda r: -len(r["涉及方向"]))
        return rows
