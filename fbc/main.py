from fbc.graph import draw_graph
from fbc.zofar.module import zofar_graph
from fbc.zofar.io.xml import read_questionnaire


def main():
    q = read_questionnaire("data/questionnaire2.xml")
    g = zofar_graph(q)
    draw_graph(g, 'graph.png')


if __name__ == "__main__":
    main()
