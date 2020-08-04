from examples.PEs.alu_basic import gen_ALU
from examples.PEs.PE_lut import gen_PE as gen_PE_lut
from lassen import PE_fc as lassen_fc
from importlib import reload  

from metamapper.irs.coreir import gen_CoreIRNodes
import metamapper.coreir_util as cutil
import metamapper.peak_util as putil
from metamapper.node import Nodes
from metamapper import CoreIRContext
from metamapper.coreir_mapper import Mapper

import delegator
import pytest
from hwtypes import BitVector, Tuple, Bit, bit_vector

from peak_gen.sim import wrapped_pe_arch_closure, pe_arch_closure
from peak_gen.arch import read_arch, graph_arch
from peak.mapper import RewriteRule
import glob, jsonpickle
import peak
import shutil 
import sys
import inspect

import peak_eq_0
import peak_eq_1
import peak_eq_2
import peak_eq_3

arch = read_arch("../DSEGraphAnalysis/outputs/subgraph_archs/subgraph_arch_merged.json")
PE_fc = pe_arch_closure(arch)

rrules = []

# breakpoint()
for ind, name in enumerate(glob.glob('../DSEGraphAnalysis/outputs/subgraph_rewrite_rules/*.json')): 

    
    print("../DSEGraphAnalysis/outputs/subgraph_rewrite_rules/subgraph_rr_" + str(ind) + ".json")
    with open("../DSEGraphAnalysis/outputs/subgraph_rewrite_rules/subgraph_rr_" + str(ind) + ".json") as json_file:
        rewrite_rule_in = jsonpickle.decode(json_file.read())

    input_binding = []

    input_binding_tmp = rewrite_rule_in["ibinding"]

    for i in input_binding_tmp:
        if i[1][0] != "fp_vals":
            if isinstance(i[0], dict):
                u = i[0]
                v = i[1]
                if u['type'] == "BitVector":
                    u = (BitVector[u['width']](u['value']))
                elif u['type'] == "Bit":
                    u = (Bit(u['value']))

                input_binding.append(tuple([u, tuple(v) ])) 
            elif i[0] == "unbound":
                input_binding.append(tuple( [peak.mapper.utils.Unbound, tuple(i[1])] ))
            else:
                input_binding.append(tuple( [tuple(i[0]), tuple(i[1])] ))
            

    output_binding_tmp = rewrite_rule_in["obinding"]
    output_binding = []

    for o in output_binding_tmp:
        output_binding.append(tuple( [tuple(o[0]), tuple(o[1])] ))

    # shutil.copyfile("../DSEGraphAnalysis/outputs/peak_eqs/peak_eq_" + str(ind) + ".py", "./tests/peak_eq.py") 
    # import peak_eq
    # peak_eq = reload(peak_eq)

    # rrules.append(RewriteRule(input_binding, output_binding, peak_eq.mapping_function_fc, PE_fc))

    # print(inspect.getsource(peak_eq))

    # exec(open("../DSEGraphAnalysis/outputs/peak_eqs/peak_eq_" + str(ind) + ".py").read())

    # peak_eq.mapping_function_fc.Py()
    # peak_eq.mapping_function_fc.Magma()

    if ind == 0:
        rrules.append(RewriteRule(input_binding, output_binding, peak_eq_0.mapping_function_fc_0, PE_fc))
        print(inspect.getsource(peak_eq_0))
    elif ind == 1:
        rrules.append(RewriteRule(input_binding, output_binding, peak_eq_1.mapping_function_fc_1, PE_fc))
        print(inspect.getsource(peak_eq_1))
    elif ind == 2:
        rrules.append(RewriteRule(input_binding, output_binding, peak_eq_2.mapping_function_fc_2, PE_fc))
        print(inspect.getsource(peak_eq_2))
    else:
        rrules.append(RewriteRule(input_binding, output_binding, peak_eq_3.mapping_function_fc_3, PE_fc))
        print(inspect.getsource(peak_eq_3))



lassen_constraints = {
    ("clk_en",): 1,
    ("config_addr",): 0,
    ("config_data",): 0,
    ("config_en",): 0,
}

@pytest.mark.parametrize("arch", [
#     ("PE_lut", gen_PE_lut(16), {}),
#     #("Lassen", lassen_fc, lassen_constraints),
#     ("ALU", gen_ALU(16), {}),
# ])
#@pytest.mark.parametrize("app", ["camera_pipeine"])#, "add2", "add1_const", "add4", "add3_const"])
#@pytest.mark.parametrize("app", ["conv_3_3"])#, "add2", "add1_const", "add4", "add3_const"])
# @pytest.mark.parametrize("app", ["add2", "add1_const", "add4", "add3_const"])

    #("PE_lut", gen_PE_lut(16), {}),
    # ("PE", PE_fc, {})
    ("Lassen", lassen_fc, lassen_constraints),
    #("ALU", gen_ALU(16), {}),
])
# @pytest.mark.parametrize("app", ["camera_pipeline"])#, "add2", "add1_const", "add4", "add3_const"])
@pytest.mark.parametrize("app", ["conv_3_3"])#, "add2", "add1_const", "add4", "add3_const"])
#@pytest.mark.parametrize("app", ["add_or"]) #, "add2", "add1_const"])

def test_app(arch, app):
    c = CoreIRContext(reset=True)
    file_name = f"examples/coreir/{app}.json"
    cutil.load_libs(["commonlib"])
    # cutil.load_libs(["lakelib"])
    CoreIRNodes = gen_CoreIRNodes(16)
    cmod = cutil.load_from_json(file_name, libraries=["lakelib"])
    pb_dags = cutil.preprocess(CoreIRNodes, cmod)
    name, arch_fc, constraints = arch

    ArchNodes = Nodes("Arch")
    putil.load_from_peak(ArchNodes, arch_fc)
    mapper = Mapper(CoreIRNodes, ArchNodes,conv=True)
    mapped_cmod = mapper.do_mapping(pb_dags)
    mapped_cmod.print_()
    c.set_top(mapped_cmod)
    c.run_passes(["cullgraph"])
    mapped_file = f"tests/build/{name}_{app}_mapped"
    mapped_cmod.save_to_file(f"{mapped_file}.json")

    #Test syntax of serialized json
    res = delegator.run(f"coreir -i {mapped_file}.json -l commonlib")
    assert not res.return_code, res.out + res.err

    #Test serializing to verilog
    res = delegator.run(f'coreir -i {mapped_file}.json -l commonlib -p "wireclocks-clk; wireclocks-arst" -o {mapped_file}.v --inline')
    assert not res.return_code, res.out + res.err

#test_app(("PE_lut", gen_PE_lut(16), {}),"add2")

