from __future__ import annotations

GRAPH_NAME = "memory_graph"


def age_setup_sql() -> str:
    return "LOAD 'age'; SET search_path = ag_catalog, \"$user\", public;"
