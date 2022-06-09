import networkx as nx
from functools import reduce
from typing import Any, List
from fbc.util import bfs_nodes
from sympy import simplify, true, false, Expr
from fbc.algebra.core import Enum


def evaluate_node_predicates(g: nx.DiGraph, source: Any, enums: List[Enum]) -> Any:
    """
    Evaluates all node predicates in `g` reachable from `source` node. As a result each node will contain a 'pred'
    attribute containing the condition to be fulfilled in order to reach the respective node.

    Each 'pred' attribute is evaluated by following one of the two rules:

    (1) if a node has no inbound edges, 'pred' is true
    (2) otherwise 'pred' is set to (['pred' of parent 1] and ['filter' of edge from parent 1]) or
                                   (['pred' of parent 2] and ['filter' of edge from parent 2]) or
                                   ...

    :param g: graph
    :param source: node to start from
    :param enums: list of enumerations regarded during evaluation
    """
    nodes = bfs_nodes(g, source=source)

    # In order to process a node, each node either needs to have no inbound edges or all parent nodes already need
    # to be evaluated. For this reason we process the nodes in breadth first search node order covering most nodes in
    # the first run. The evaluation is then repeated until all nodes are covered.
    while len(nodes) != 0:
        processed_nodes = set()

        for v in nodes:
            in_edges = g.in_edges(v, data=True)

            if len(in_edges) == 0:
                g.nodes[v].update({"pred": true})

                processed_nodes.add(v)
            elif all(['pred' in g.nodes[v_parent] for v_parent, _, _ in in_edges]):
                # check if all parent nodes are already evaluated

                # get parent predicate and edge filter for all inbound edges
                in_nodes = [(g.nodes[v_parent]['pred'], g.edges[v_parent, v_child]['filter'])
                            for v_parent, v_child, data in in_edges]

                # determine node predicate via conjunction of each `node predicate`-`edge filter` pair and
                # disjunction of those results
                node_pred = simplify_enums(simplify(reduce(lambda res, p: res | (p[0] & p[1]), in_nodes, false)), enums)
                g.nodes[v].update({"pred": node_pred})

                processed_nodes.add(v)

        if len(processed_nodes) == 0:
            raise ValueError("Could not process in evaluating node predicates")

        nodes = [v for v in nodes if v not in processed_nodes]


def graph_soundness_check(g: nx.Graph, source: Any, enums: List[Enum]) -> bool:
    """
    Checks weather the `soundness_check` applies to all nodes in the graph

    :param g: graph
    :param source: node to start from
    :param enums: list of enumerations regarded during evaluation
    :return: True, if the `soundness_check` applies to all nodes in the graph
    """
    return all([soundness_check(g, v, enums) for v in bfs_nodes(g, source)])


def soundness_check(g: nx.Graph, v: Any, enums: List[Enum]) -> bool:
    """
    Checks weather the disjunction of all outbound edge filters of a node is True.

    :param g: graph
    :param v: node to evaluate
    :param enums: list of enumerations regarded during evaluation
    :return: True, if the disjunction of all outbound edge filters of the node is True
    """
    out_predicates = [d['filter'] for d in g[v].values()]
    if len(out_predicates) != 0:
        return simplify_enums(simplify(reduce(lambda a, b: a | b, out_predicates)), enums) == true
    else:
        return True


def simplify_enums(exp: Expr, enums: List[Enum]) -> Expr:
    """
    Simplifies given expression with regard to given enums. For each enum it is checked, if for all enum
    members the expression becomes true. In this case this enum is removed from the expression

    :param exp: expression
    :param enums: list of enumerations regarded during evaluation
    :return: simplified expression
    """
    for i in range(len(enums)):
        enum = enums[i]
        other_enums = enums[:i] + enums[i+1:]
        # combined null substitution for all `other_enums`
        null_subs = reduce(lambda a, b: {**a, **b.null_subs}, other_enums, {})

        if all([exp.subs({**null_subs, **enum.subs(m)}) == true for m in enum.members]):
            exp = exp.subs(enum.null_subs)

    return exp
