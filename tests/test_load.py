import coreir
from metamapper import load_coreir_module
from metamapper.visitor import Visitor

def test_load_add():
    c = coreir.Context()
    mod = c.load_from_file("examples/add4.json")
    expr = load_coreir_module(mod) 
    assert len(expr.inputs) == 4
    for i in range(4):
        assert expr.inputs[i].port_name == f"in{i}"
    assert len(expr.outputs) == 1
    assert expr.outputs[0].port_name == "out"

    class AddID(Visitor):
        def __init__(self, dag):
            self.curid = 0
            super().__init__(dag)

        def generic_visit(self, node):
            node._id_ = self.curid
            self.curid +=1
            Visitor.generic_visit(self, node)

    class Printer(Visitor):
        def generic_visit(self, node):
            child_ids = ", ".join([str(child._id_) for child in node.children()])
            print(f"{node._id_}<{node.iname}>({child_ids})")
            Visitor.generic_visit(self, node)

        def visit_Input(self, node):
            print(f"{node._id_}<Input:{node.port_name}>")
            Visitor.generic_visit(self, node)

        def visit_Output(self, node):
            child_ids = ", ".join([str(child._id_) for child in node.children()])
            print(f"Output:{node.port_name}({child_ids})")
            Visitor.generic_visit(self, node)

    AddID(expr)
    Printer(expr)
