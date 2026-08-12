import docutils.nodes
from docutils.core import publish_doctree


class Visitor:
    def visit(self, node: docutils.nodes.Node):
        method = getattr(self, "visit_" + node.__class__.__name__, self.default_visit)
        return method(node)

    def default_visit(self, node: docutils.nodes.Node):
        for child in node.children:
            self.visit(child)


# noinspection method-may-be-static
class MyVisitor(Visitor):
    def __init__(self):
        self.field_docs = {}
        self.natural_paragraphs = []

        self.field_name = None
        self.field_body = []

        self.has_find_field_list = False

        self.list_term = None

        self.in_field = False

    def visit_paragraph(self, node):
        if self.in_field:
            return node.astext()
        elif not self.has_find_field_list:
            self.natural_paragraphs.append(node.astext())
        else:
            self.field_docs[self.field_name].append(node.astext())

    def visit_field_name(self, node):
        self.field_name = node.astext()

    def visit_field_body(self, node: docutils.nodes.field_body):
        parts = []
        self.in_field = True
        for child in node.children:
            parts.append(self.visit(child))
        self.in_field = False

        self.field_body = parts

    def visit_term(self, node):
        self.list_term = node.astext()

    def visit_bullet_list(self, node):
        assert self.list_term

        parts = [self.list_term]
        for child in node.children:
            parts.append(self.visit(child))

        if self.in_field:
            return '\n'.join(parts)
        elif not self.has_find_field_list:
            self.natural_paragraphs.extend(parts)
            return None
        else:
            self.field_docs[self.field_name].extend(parts)
            return None

    def visit_list_item(self, node):
        return f'- {node.astext()}'

    def visit_field(self, node):
        self.default_visit(node)
        self.field_docs[self.field_name] = self.field_body

    def visit_field_list(self, node):
        self.has_find_field_list = True
        self.default_visit(node)


def process_func_doc(docstring) -> tuple[str, dict[str, str]]:
    """
    处理函数文档
    分析函数文档，分离和整合自然段和 REST 标记部分，并返回

    :param docstring:
    :return: 一个二元组 (<自然段落字符串（已整理>, <参数文档字典>)
    """
    if not docstring:
        return "", {}

    try:
        tree = publish_doctree(docstring)
    except Exception as exc:
        # logger.opt(exception=exc).error(str(exc))
        return "", {}

    # print(tree.pformat())

    visitor = MyVisitor()
    visitor.visit(tree)

    field_docs = {
        k.removeprefix('param '): '\n\n'.join(v)
        for k, v in visitor.field_docs.items()
    }

    # print(field_docs)

    return '\n\n'.join(visitor.natural_paragraphs), field_docs
