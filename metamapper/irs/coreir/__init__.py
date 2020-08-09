from .ir import gen_peak_CoreIR
from ...node import Nodes, DagNode, Select
from ... import CoreIRContext
from ...peak_util import load_from_peak
import coreir

def strip_trailing(op):
    if op[-1] == "_":
        return op[:-1]
    return op
def gen_CoreIRNodes(width):
    CoreIRNodes = Nodes("CoreIR")
    peak_ir = gen_peak_CoreIR(width)
    c = CoreIRContext()

    basic = ("mul", "add", "const", "and_", "or_")
    other = ("ashr", "eq", "lshr", "mux", "sub", "slt", "sle", "sgt", "sge", "ult", "ule", "ugt", "uge")
    bit_ops = ("const", "or_", "and_", "xor", "not_")
    commonlib_ops = ("abs", "smax", "smin", "umin", "umax")
    for namespace, ops, is_module in (
        ("coreir", basic + other, False),
        ("corebit", bit_ops, True),
        ("commonlib", commonlib_ops, False)
    ):
        for op in ops:
            assert c.get_namespace(namespace) is c.get_namespace(namespace)
            name = f"{namespace}.{op}"
            peak_fc = peak_ir.instructions[name]
            coreir_op = strip_trailing(op)
            if is_module:
                cmod = c.get_namespace(namespace).modules[coreir_op]
            else:
                gen = c.get_namespace(namespace).generators[coreir_op]
                cmod = gen(width=width)
            name_ = load_from_peak(CoreIRNodes, peak_fc, cmod=cmod, name=name)
            assert name_ == name
            assert name in CoreIRNodes.coreir_modules
            assert CoreIRNodes.name_from_coreir(cmod) == name
            print(f"Loaded {name}!")



    class Rom(DagNode):
        def __init__(self, raddr, ren, *, init, iname):
            super().__init__(raddr, ren, init=init, iname=iname)

        @property
        def attributes(self):
            return ("init", "iname")

        #Hack to get correct port name
        def select(self, field):
            self._selects.add("rdata")
            return Select(self, field="rdata")

        nodes = CoreIRNodes
        node_name = "memory.rom2"
        num_children = 2

    rom2 = CoreIRContext().get_namespace("memory").generators["rom2"](depth=255, width=width)

    CoreIRNodes.add("memory.rom2", peak_ir.instructions["memory.rom2"], rom2, Rom)
    assert "memory.rom2" in CoreIRNodes.dag_nodes
    assert CoreIRNodes.dag_nodes["memory.rom2"] is not None
    return CoreIRNodes

