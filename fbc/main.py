import networkx as nx
from sympy import symbols, true
from fbc.eval import graph_soundness_check, evaluate_node_predicates
from fbc.util import show_graph


def main():
    p1, p2, p3, p4, p5 = symbols("p1 p2 p3 p4 p5")

    g = nx.DiGraph()
    g.add_nodes_from([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    g.add_edges_from([(1, 2, {"filter": p1 > 0}),
                      (1, 3, {"filter": p1 <= 0}),
                      (2, 4, {"filter": p2}),
                      (2, 5, {"filter": ~p2}),
                      (3, 6, {"filter": p3}),
                      (3, 7, {"filter": ~p3}),
                      (4, 8, {"filter": true}),
                      (5, 8, {"filter": p4}),
                      (5, 10, {"filter": ~p4}),
                      (6, 9, {"filter": true}),
                      (7, 9, {"filter": true}),
                      (8, 10, {"filter": true}),
                      (9, 10, {"filter": true}),
                      (11, 3, {"filter": true}),
                      (1, 11, {"filter": p5}),
                      (1, 12, {"filter": ~p5}),
                      (12, 3, {"filter": true})
                      ])

    if not graph_soundness_check(g, source=1):
        raise ValueError("Soundness check failed")

    evaluate_node_predicates(g, source=1)

    if g.nodes[10]['pred'] is not true:
        raise ValueError(f"Graph evaluation failed: final node cannot be reached unless '{g.nodes[10]['pred']}'")

    show_graph(g)


if __name__ == "__main__":
    main()
