from fbc.zofar.env import construct_graph
from fbc.util import draw_graph, show_graph
from fbc.zofar.io.xml import read_questionnaire


def main():
    q = read_questionnaire("data/questionnaire2.xml")
    g = construct_graph(q)
    show_graph(g)


if __name__ == "__main__":
    main()
