import networkx as nx
from networkx import bfs_edges
from PIL import Image
import io
from pygraphviz.agraph import AGraph
from typing import List, Any, Optional
from contextlib import contextmanager
import time





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
