import networkx as nx
from networkx import bfs_edges
from PIL import Image
import io
from pygraphviz.agraph import AGraph
from typing import List, Any, Optional
from contextlib import contextmanager
import time


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


def flatten(ll):
    """
    Flattens given list of lists by one level

    :param ll: list of lists
    :return: flattened list
    """
    return [it for li in ll for it in li]


def group_by(li, key, val=None):
    if val is None:
        val = lambda x: x

    g = {}
    for i in li:
        k = key(i)
        if k not in g:
            g[k] = []
        g[k].append(val(i))
    return g


class Timer(object):
    """
    A simple timer for performance logs

    E.g.
    >> t = Timer()
    >> time.sleep(1)
    >> print(t)
    1.00007120262146
    >> print(f"Completed in {t:5.3f}")
    Completed in 1.000
    """
    def __init__(self, start: Optional[float] = None):
        """
        Initialize a timer
        :param start: Sets the start/reference time manually (default time.time())
        """
        if start is None:
            start = time.time()
        self.start = start

    def reset(self, start: Optional[float] = None) -> None:
        """
        Resets the timer
        :param start: Set the new start/reference time manually (default time.time())
        """
        if start is None:
            start = time.time()
        self.start = start

    def __float__(self) -> float:
        return self.time_diff()

    def __repr__(self) -> str:
        return str(self.time_diff())

    def __format__(self, format_spec) -> str:
        return self.time_diff().__format__(format_spec)

    def time_diff(self, t: Optional[float] = None) -> float:
        """
        Returns time diff between start time and current time
        :param t: Manually set a time to compare with (default time.time())
        :return: time diff between start and current time
        """
        if t is None:
            t = time.time()

        return t - self.start


@contextmanager
def timer(start=None):
    """
    Context manager for time measurements.

    E.g.
    >> with timer() as t:
    >>     time.sleep(1)
    >>     print(f"Completed in {t:5.3f}")
    Completed in 1.000

    :param start: Sets the start/reference time manually (default time.time())
    """
    t = Timer(start)
    yield t
