from lxml import objectify
# ToDo: implement DiGraph creation
from networkx import DiGraph
from pathlib import Path
from dataclasses import dataclass, field
from collections.abc import Iterable

_here = Path(__file__).parent

VARIABLE_TYPES = ['string', 'boolean', 'singleChoice']
QUESTION_TYPES = ['questionOpen', 'multipleChoice', 'questionSingleChoice', 'multipleChoiceMatrix',
                  'singleChoiceMatrix', 'section']
ZOFAR_NAMESPACE = '{http://www.his.de/zofar/xml/questionnaire}'
NAMESPACE_QUESTION_TYPES = [ZOFAR_NAMESPACE + TYPE for TYPE in QUESTION_TYPES]


def read_xml(input_path: Path) -> objectify.ObjectifiedElement:
    return objectify.fromstring(input_path.read_bytes())


@dataclass
class Transition:
    page_uid: str
    target_uid: str
    transition_condition: str


@dataclass
class Variable:
    page_uid: str
    variable_name: str
    type: str
    visible_condition: str = 'true'
    is_preload: bool = False
    is_computed: bool = False

    def __eq__(self, other):
        if isinstance(other, Variable) and \
                self.page_uid == other.page_uid and \
                self.variable_name == other.variable_name and \
                self.type == other.type and \
                self.visible_condition == other.visible_condition and \
                self.is_preload == other.is_preload and \
                self.is_computed == other.is_computed:
            return True
        else:
            return False


@dataclass
class QmlPage:
    page_uid: str
    variables_list: list = field(default_factory=lambda: [])
    transitions: tuple = tuple()

    def add_transition(self, transition: Transition):
        self.transitions = self.transitions + tuple([transition])

    def add_variable(self, variable: Variable):
        if variable not in self.variables_list:
            self.variables_list.append(variable)


class Questionnaire(dict):
    def add_variable(self, variable: Variable) -> None:
        if variable.page_uid not in self.keys():
            self[variable.page_uid] = QmlPage(page_uid=variable.page_uid,
                                              variables_list=[variable])
        else:
            self[variable.page_uid].add_variable(variable)

    def add_page(self, page: QmlPage):
        if page.page_uid not in self.keys():
            self[page.page_uid] = page

    def add_transition_tuple(self, transition_tuple: tuple) -> None:
        if len(transition_tuple) == 0:
            return
        page_uid = transition_tuple[0].page_uid
        if page_uid in self.keys():
            if self[page_uid].transitions != tuple([]):
                raise ValueError(f'Transitions for page {page_uid=} are already present: {self[page_uid].transitions=}')
            else:
                self[page_uid].transitions = transition_tuple
        else:
            self.add_page(QmlPage(page_uid=page_uid,transitions=transition_tuple))


def find_variables_in_descendants(element: objectify.ObjectifiedElement,
                                  visible_condition: str,
                                  page_uid: str) -> list:
    visible_condition = visible_condition.strip()
    tmp_visible_condition = ""
    tmp_list = []
    if element.tag in NAMESPACE_QUESTION_TYPES:
        if 'visible' in element.attrib:
            tmp_visible_condition = element.attrib['visible'].strip()
        else:
            tmp_visible_condition = 'true'

        # keep visible_condition as already 'true' if both are 'true'
        if visible_condition == 'true' and tmp_visible_condition == 'true':
            pass
        # keep visible_condition if tmp_visible_condition is 'true'
        elif visible_condition != 'true' and tmp_visible_condition == 'true':
            pass
        # set visible_condition to the value of tmp_visible_condition
        elif visible_condition == 'true' and tmp_visible_condition != 'true':
            visible_condition = tmp_visible_condition
        # any other case: user conjunction of both
        else:
            visible_condition = f'({visible_condition}) and ({tmp_visible_condition})'
    if 'variable' in element.attrib:
        # ToDo: uses global variable - don't forget that when refactoring!!
        variable_name = element.attrib['variable']
        variable = Variable(page_uid=page_uid,
                            variable_name=variable_name,
                            type=var_type_dict[element.attrib['variable']],
                            visible_condition=visible_condition)
        tmp_list.append(variable)
    for child_element in element.iterchildren():
        tmp_list += (find_variables_in_descendants(element=child_element,
                                                   visible_condition=visible_condition,
                                                   page_uid=page_uid))
    return tmp_list


def variables_on_page_body(page: objectify.ObjectifiedElement) -> list:
    page_uid = page.attrib['uid']
    variables_list = []
    if hasattr(page, 'body'):
        variables_list += (find_variables_in_descendants(page.body, visible_condition='true', page_uid=page_uid))
    return variables_list


def variables_type_dict(root: objectify.ObjectifiedElement) -> dict:
    variables_type_dictionary = {}
    if hasattr(root, 'variables'):
        for variable in root.variables.iterchildren():
            if variable.tag == 'comment':
                continue
            if 'name' in variable.attrib and 'type' in variable.attrib:
                variables_type_dictionary[variable.attrib['name']] = variable.attrib['type']
    return variables_type_dictionary


def list_of_preload_variables(root: objectify.ObjectifiedElement) -> list:
    variables_list = []
    if hasattr(root, 'preloads'):
        for element in root.preloads.iterchildren():
            if hasattr(element, 'preloadItem'):
                for preload_element in element.preloadItem:
                    if 'variable' in preload_element.attrib:
                        variable = Variable(page_uid='index',
                                            variable_name='PRELOAD' + preload_element.attrib['variable'],
                                            type='string', is_preload=True)
                        variables_list.append(variable)
        return variables_list
    else:
        return variables_list


def page_transitions(page_object: objectify.ObjectifiedElement) -> tuple:
    page_uid = page_object.attrib['uid']
    page_transitions_tuple = []
    if hasattr(page_object, 'transitions'):
        for transition_element in page_object.transitions.iterchildren():
            if 'condition' in transition_element.attrib:
                transition_condition = transition_element.attrib['condition']
            else:
                transition_condition = 'true'
            page_transitions_tuple += tuple([Transition(page_uid=page_uid,
                                                        target_uid=transition_element.attrib['target'],
                                                        transition_condition=transition_condition)])
    return tuple(page_transitions_tuple)


def page_generator(root: objectify.ObjectifiedElement) -> Iterable:
    return (page_element for page_element in root.page)


if __name__ == '__main__':
    xml_input_file = Path(_here.parent, r'data/questionnaire.xml')
    xml_root = read_xml(xml_input_file)

    # init questionnaire object
    questionnaire = Questionnaire()

    # find preloads
    preloads = list_of_preload_variables(root=xml_root)

    # add preload variables to index page
    [questionnaire.add_variable(variable) for variable in preloads]

    # generate variables_type_dict
    var_type_dict = variables_type_dict(root=xml_root)

    # iterate over all pages
    for page in page_generator(root=xml_root):
        for variable in variables_on_page_body(page=page):
            questionnaire.add_variable(variable)
        questionnaire.add_transition_tuple(page_transitions(page_object=page))

        print()
    print()
