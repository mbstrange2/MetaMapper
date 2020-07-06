import coreir
from DagVisitor import Visitor, Transformer
from collections import OrderedDict
from .node import DagNode, Dag, Nodes, Source, Sink, Input, Combine, Constant
from . import CoreIRContext
import typing as tp
from peak import family
from peak.mapper import Unbound
from peak.assembler import AssembledADT, Assembler, AssembledADTRecursor
from .common_passes import print_dag
from hwtypes.adt import Product, Enum
from peak.family import PyFamily
import os


#returns input objects and output objects
def parse_rtype(rtype) -> tp.Mapping[str, coreir.Type]:
    assert isinstance(rtype, coreir.Record)
    inputs = OrderedDict()
    outputs = OrderedDict()
    for n, t in rtype.items():
        if t.kind == "Named":
            continue
        if t.kind not in ("Array", "Bit", "BitIn"):
            raise NotImplementedError()
        if t.is_input():
            inputs[n] = t
        elif t.is_output():
            outputs[n] = t
        else:
            raise ValueError("Bad io type!")

    #Filter out "ASYNCRESET" and "CLK"
    for d in (inputs, outputs):
        for name in ("ASYNCRESET", "CLK"):
            if name in d:
                del d[name]
    return inputs, outputs


def adt_to_ctype(adt):
    c = CoreIRContext()
    if issubclass(adt, PyFamily().BitVector):
        return c.Array(adt.size, c.Bit())
    elif issubclass(adt, PyFamily().Bit):
        return c.Bit()
    elif issubclass(adt, Enum):
        aadt_t = AssembledADT[adt, Assembler, PyFamily().BitVector]
        adt_t, assembler_t, _ = aadt_t.fields
        width = assembler_t(adt_t).width
        return c.Array(width, c.Bit())
    elif issubclass(adt, Product):
        fields = OrderedDict()
        for field, sub_adt in adt.field_dict.items():
            fields[field] = adt_to_ctype(sub_adt)
        return c.Record(fields)
    else:
        raise NotImplementedError(str(adt))

class Loader:
    def __init__(self, cmod: coreir.Module, nodes: Nodes):
        self.cmod = cmod
        self.nodes = nodes
        self.c = cmod.context
        self.node_map: tp.Mapping[coreir.Instance, str] = {}

        #Verify all instances are from particular nodes
        #TODO Find all stateful instances
        source_nodes = [Input(iname="self")]
        stateful_instances = [cmod.definition.interface]
        for inst in cmod.definition.instances:
            node_name = self.nodes.name_from_coreir(inst.module)
            if node_name is None:
                raise ValueError(f"{inst.module.name} was never loaded into {self.nodes}")
            if self.nodes.is_stateful(node_name):
                source, sink = self.nodes.dag_nodes[node_name]
                source_nodes.append(source(iname=inst.name))
                stateful_instances.append(inst)

        #inputs, outputs = parse_rtype(cmod.type)

        # load up node_map with source nodes
        for source, inst in zip(source_nodes, stateful_instances):
            self.node_map[inst] = source

        #create all the sinks
        sink_nodes = []
        for source, inst in zip(source_nodes, stateful_instances):
            sink_t = type(source).sink_t
            sink_node = self.add_node(inst, sink_t=sink_t)
            assert isinstance(sink_node, DagNode)
            sink_nodes.append(sink_node)
        self.dag = Dag(source_nodes, sink_nodes)

    def add_node(self, inst: coreir.Instance, sink_t=None):
        if sink_t is None and inst in self.node_map:
            return self.node_map[inst]
        if sink_t is None:
            node_name = self.nodes.name_from_coreir(inst.module)
            node_t = self.nodes.dag_nodes[node_name]
            assert issubclass(node_t, DagNode)
        else:
            node_t = sink_t
        children = []
        for child_inst, port in self.get_drivers(inst):
            if (child_inst, port) == (None, None):
                children.append(Constant(value=Unbound))
            else:
                child_node = self.add_node(child_inst)
                children.append(child_node.select(port))

        if inst is self.cmod.definition.interface:
            iname = "self"
        else:
            modargs = [Constant(value=v.value) for k, v in inst.config.items()]
            #TODO unsafe. Assumes that modargs are specified at the end.
            children += modargs
            iname = inst.name
        node = node_t(*children, iname=iname)
        if sink_t is None:
            self.node_map[inst] = node
        return node

    def inst_from_name(self, iname):
        if iname == "self":
            return self.cmod.definition.interface
        else:
            return self.cmod.definition.get_instance(iname)

    def inst_to_type(self, inst: coreir.Instance) -> coreir.Record:
        if inst is self.cmod.definition.interface:
            T = self.c.Flip(self.cmod.type)
        else:
            T = inst.module.type
        return T

    def get_drivers(self, inst: tp.Union[coreir.Instance, coreir.Interface]) -> tp.List[tp.Tuple[coreir.Instance, str]]:

        if inst is self.cmod.definition.interface:
            outputs, inputs = parse_rtype(self.cmod.type)
        else:
            inputs, outputs = parse_rtype(inst.module.type)
        drivers = []
        for port_name, t in inputs.items():
            port = inst.select(port_name)
            conns = port.connected_wireables
            if len(conns) == 0:
                drivers.append((None, None))
            else:
                assert len(conns) == 1, f"{len(conns)}, {port}"
                driver = conns[0]
                dpath = driver.selectpath
                assert len(dpath) == 2
                driver_iname, driver_port = dpath[0], dpath[1]
                driver_inst = self.inst_from_name(driver_iname)
                drivers.append((driver_inst, driver_port))
        return drivers

def coreir_to_dag(nodes: Nodes, cmod):
    return Loader(cmod, nodes).dag

#returns module, and map from instances to dags
def load_from_json(file, libraries=[]):
    if not os.path.isfile(file):
        raise ValueError(f"{file} does not exist")
    c = CoreIRContext()
    for lib in libraries:
        c.load_library(lib)
    cmod = c.load_from_file(file)
    return cmod

def preprocess(CoreIRNodes: Nodes, cmod: coreir.Module) -> tp.Mapping[coreir.Instance, Dag]:
    #First inline all commonlib instances (rungenerators for commonlib first)
    #TODO

    c = cmod.context
    #Run isolate_primitives pass
    c.run_passes(["isolate_primitives"])
    #Find all instances of modules which need to be mapped (All the _.*primitives) modules
    primitive_blocks = []
    assert cmod.definition
    for inst in cmod.definition.instances:
        ns_name = inst.module.namespace.name
        if ns_name == "_":
            primitive_blocks.append(inst)

    #dagify all the primitive_blocks
    pb_dags = {inst:coreir_to_dag(CoreIRNodes, inst.module) for inst in primitive_blocks}
    return pb_dags

class ToCoreir(Visitor):
    def __init__(self, nodes: Nodes, def_: coreir.ModuleDef):
        self.coreir_const = CoreIRContext().get_namespace("coreir").generators["const"]
        self.coreir_bit_const = CoreIRContext().get_namespace("corebit").modules["const"]
        self.coreir_pt = CoreIRContext().get_namespace("_").generators["passthrough"]
        self.nodes = nodes
        self.def_ = def_
        self.node_to_inst: tp.Mapping[DagNode, coreir.Wireable] = {}  # inst is really the output port of the instance

    def doit(self, dag: Dag):
        #Create all the instances for the Source/Sinks first
        for sink in list(dag.roots())[1:]:
            inst = self.create_instance(sink)
            self.node_to_inst[sink] = inst
            self.node_to_inst[sink.source] = inst
        self.run(dag)

    def visit_Select(self, node):
        Visitor.generic_visit(self, node)
        child_inst = self.node_to_inst[node.children()[0]]
        self.node_to_inst[node] = child_inst.select(node.field)

    def visit_Input(self, node):
        self.node_to_inst[node] = self.def_.interface

    def visit_Source(self, node):
        assert node.sink in self.node_to_inst
        self.node_to_inst[node] = self.node_to_inst[node.sink]

    def visit_Constant(self, node):
        assert isinstance(node, Constant)
        bv_val = node.value
        if bv_val is Unbound:
            self.node_to_inst[node] = None
            return
        is_bool = type(bv_val) is bool
        if is_bool:
            const_mod = self.coreir_bit_const
        else:
            const_mod = self.coreir_const(width=bv_val.size)
        config = CoreIRContext().new_values(fields=dict(value=bv_val))
        iname = "c" + str(id(node))
        inst = self.def_.add_module_instance(iname, const_mod, config=config)
        self.node_to_inst[node] = inst.select("out")

    def visit_Combine(self, node: Combine):
        Visitor.generic_visit(self, node)
        def create_pt(cinputs):
            rtype = CoreIRContext().Record(cinputs)
            assert isinstance(rtype, coreir.Record)
            pt_mod = self.coreir_pt(type=rtype)
            return pt_mod

        pt_mod = create_pt(node.cinputs)
        pt_inst = self.def_.add_module_instance(node.iname, pt_mod)
        for path, child in zip(node.selects, node.children()):
            child_inst = self.node_to_inst[child]
            pt_sel = pt_inst.select("in")
            for field in path:
                pt_sel = pt_sel.select(field)
            self.def_.connect(child_inst, pt_sel)
        self.node_to_inst[node] = pt_inst.select("out")

    def create_instance(self, node):
        if node in self.node_to_inst:
            return self.node_to_inst[node]
        cmod_t = self.nodes.coreir_modules[type(node).node_name]
        # create new instance
        #create modparams
        children = list(node.children())
        config_fields = {}
        for param in reversed(type(node).modparams):
            child = children.pop(-1)
            assert isinstance(child, Constant)
            bv_val = child.value
            if bv_val is Unbound:
                continue
            config_fields[param] = bv_val
        if len(config_fields) > 0:
            config = CoreIRContext().new_values(fields=config_fields)
            inst = self.def_.add_module_instance(node.iname, cmod_t, config=config)
        else:
            inst = self.def_.add_module_instance(node.iname, cmod_t)
        return inst

    def generic_visit(self, node):
        Visitor.generic_visit(self, node)
        inst = self.create_instance(node)
        inst_inputs = list(self.nodes.peak_nodes[node.node_name](family.PyFamily()).input_t.field_dict.keys())
        # Wire all the children (inputs)
        #Get only the non-modparam children
        children = list(node.children())[:-len(node.modparams)]
        for port, child in zip(inst_inputs, children):
            if type(node).node_name == "coreir_reg" and port == "in0":
                port = "in"
            child_inst = self.node_to_inst[child]
            if child_inst is not None:
                self.def_.connect(child_inst, inst.select(port))
        self.node_to_inst[node] = inst

    #The issue is that output is visited first then the source, then the sink. Depth first vs breadth first.

    def visit_Output(self, node):
        Visitor.generic_visit(self, node)

        _, outputs = parse_rtype(self.def_.module.type)
        io = self.def_.interface
        # Wire all the children (inputs)
        for port, child in zip(outputs.keys(), node.children()):
            child_inst = self.node_to_inst[child]
            if child_inst is not None:
                self.def_.connect(child_inst, io.select(port))

    #I want to solve this for a generic Source/Sink Pair and not special case to registers
    #CoreIR Registers have modparams. These are gotten from the Sink part of the pair.



class VerifyUniqueIname(Visitor):
    def __init__(self):
        self.inames = {}

    def generic_visit(self, node):
        Visitor.generic_visit(self, node)
        if node.iname in self.inames:
            raise ValueError(f"{node.iname} for {node} already used by {self.inames[node.iname]}")
        self.inames[node.iname] = node

    def visit_Source(self, node):
        pass

# Magma compiles output ports into either "O" for single outputs or "O0", "O1" etc for multi-output
# This pass replaces non-input selects to the better name
class FixSelects(Transformer):
    def __init__(self, nodes):
        self.field_map = {}
        for node_name in nodes._node_names:
            peak_fc = nodes.peak_nodes[node_name]
            dag_node = nodes.dag_nodes[node_name]
            if nodes.is_stateful(node_name):
                dag_node = dag_node[0] #Use the source
            assert issubclass(dag_node, DagNode), f"{dag_node}"
            peak_outputs = list(peak_fc(family.PyFamily()).output_t.field_dict.keys())
            if len(peak_outputs) == 1:
                self.field_map[dag_node] = {peak_outputs[0]: "O"}
            else:
                self.field_map[dag_node] = {name: f"O{i}" for i, name in enumerate(peak_outputs)}

    def visit_Select(self, node):
        Transformer.generic_visit(self, node)
        child = node.children()[0]
        if isinstance(child, (Source, Combine)):
            return None
        assert type(child) in self.field_map
        replace_field = self.field_map[type(child)][node.field]
        return child.select(replace_field)

        # Create a map from field to coreir field

#This will construct a coreir module from the dag with ref_type
def dag_to_coreir_def(nodes: Nodes, dag: Dag, ref_mod: coreir.Module) -> coreir.ModuleDef:
    VerifyUniqueIname().run(dag)
    FixSelects(nodes).run(dag)
    def_ = ref_mod.new_definition()
    ToCoreir(nodes, def_).doit(dag)
    return def_
