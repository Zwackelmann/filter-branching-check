import networkx as nx
from functools import reduce
from typing import Any, List, Dict, Tuple
from fbc.util import flatten
from sympy import false, Expr, And, true, Not, simplify
from fbc.algebra.core import Enum
from fbc.lisp.env import LispEnv
from networkx import bfs_edges
from PIL import Image
import io
from pygraphviz.agraph import AGraph


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


def bfs_nodes(g: nx.Graph, source: Any) -> List[Any]:
    """
    Returns nodes in breadth first search order

    :param g: graph
    :param source: node to start from
    :return: list of nodes
    """
    return [source] + [v for _, v in bfs_edges(g, source=source)]


def to_agraph(g: nx.Graph) -> AGraph:
    """
    Converts an `nx.Graph` to an `pygraphviz.agraph.AGraph`
    :param g: nx.Graph
    :return: pygraphviz.agraph.AGraph
    """
    tmp_g = g.copy()

    # add edge 'filter' labels
    for u, v, data in tmp_g.edges(data=True):
        tmp_g.update(edges=[(u, v, {"label": (str(data["filter"]) if 'filter' in data else "")})])

    # add node 'pred' labels
    for u, data in tmp_g.nodes(data=True):
        tmp_g.update(nodes=[(u, {"label": f"{u}\n{(data['pred'] if 'pred' in data else '')}"})])

    # convert to agraph
    agraph = nx.nx_agraph.to_agraph(tmp_g)
    agraph.node_attr['shape'] = 'box'
    agraph.layout(prog='dot')

    return agraph


def draw_graph(g: nx.Graph, *args, **kwargs) -> None:
    """
    Draw a nx.Graph to a file. Uses the signature of `pygraphviz.agraph.AGraph.draw`

    :param g: graph
    :param args: args passed to `pygraphviz.agraph.AGraph.draw`
    :param kwargs: kwargs passed to `pygraphviz.agraph.AGraph.draw`
    """
    to_agraph(g).draw(*args, **kwargs)


def show_graph(g: nx.Graph, image_format='png') -> None:
    """
    Show a nx.Graph in a pillow window

    :param g: graph
    :param image_format: image format to use
    """
    agraph = to_agraph(g)
    image_data = agraph.draw(format=image_format)
    image = Image.open(io.BytesIO(image_data))
    image.show()


def transition_graph(env: LispEnv, transitions: Dict[str, List[Tuple[str, str]]]):
    nodes = set()
    nodes.update(transitions.keys())
    nodes.update(flatten([[target for _, target in trans_list] for trans_list in transitions.values()]))

    g = nx.DiGraph()
    g.add_nodes_from(nodes)

    edges = []
    for source_node_id, node_transitions in transitions.items():
        neg_trans_filters = []
        for cond, target_node_id in node_transitions:
            if cond is not None:
                trans_filter = env.eval(cond)
            else:
                trans_filter = true

            excluding_trans_filter = simplify(And(*neg_trans_filters + [trans_filter]))
            edges.append((source_node_id, target_node_id, {'filter': excluding_trans_filter}))
            neg_trans_filters.append(Not(trans_filter))

    g.add_edges_from(edges)

    return g
