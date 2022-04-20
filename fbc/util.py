import networkx as nx
from networkx import bfs_edges
from PIL import Image
import io
from pygraphviz.agraph import AGraph
from typing import List, Any


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
