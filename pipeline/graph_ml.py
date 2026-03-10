"""
NetworkX-based supply chain network risk analysis.
Computes betweenness centrality and cascade risk on the supplier graph.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)

def compute_network_risk(nodes: list[dict], edges: list[dict]) -> dict[str, Any]:
    """
    Given nodes/edges dicts (from network._build_graph()), compute:
    - betweenness centrality
    - degree centrality
    - cascade_risk_score = betweenness * in_degree

    Returns dict keyed by node_id with risk metrics.
    """
    try:
        import networkx as nx
        G = nx.DiGraph()
        for node in nodes:
            G.add_node(node["id"], **{k: v for k, v in node.items() if k != "id"})
        for edge in edges:
            G.add_edge(edge["source"], edge["target"])

        betweenness = nx.betweenness_centrality(G, normalized=True)
        degree_c = nx.degree_centrality(G)

        results = {}
        for node_id in G.nodes():
            in_deg = G.in_degree(node_id)
            bc = betweenness.get(node_id, 0.0)
            results[node_id] = {
                "betweenness": round(bc, 4),
                "degree": round(degree_c.get(node_id, 0.0), 4),
                "cascade_risk": round(bc * in_deg, 4),
            }
        return results
    except ImportError:
        logger.warning("networkx not installed — using degree-based risk fallback")
        from collections import Counter
        target_counts = Counter(e["target"] for e in edges)
        results = {}
        for node in nodes:
            nid = node["id"]
            deg = target_counts.get(nid, 0)
            results[nid] = {"betweenness": 0.0, "degree": deg / max(len(nodes), 1), "cascade_risk": float(deg)}
        return results
