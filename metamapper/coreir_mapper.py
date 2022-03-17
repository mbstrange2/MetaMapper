from metamapper.common_passes import VerifyNodes, print_dag, count_pes, CustomInline, SimplifyCombines, RemoveSelects, prove_equal, \
    Clone, ExtractNames, Unbound2Const, gen_dag_img, ConstantPacking
import metamapper.coreir_util as cutil
from metamapper.rewrite_table import RewriteTable
from metamapper.node import Nodes, Dag
from metamapper.delay_matching import DelayMatching, KernelDelay
from metamapper.instruction_selection import GreedyCovering
from peak.mapper import RewriteRule as PeakRule, read_serialized_bindings
import typing as tp
import coreir
import json


class DefaultLatency:

    @staticmethod
    def get(node):
        return 0

class Mapper:
    # Lazy # Discover at mapping time
    # ops (if lazy=False, search for these)
    # rule_file #pointer to serialized rule file
    def __init__(self, CoreIRNodes: Nodes, ArchNodes: Nodes, alg=GreedyCovering, lazy=True, ops=None, rule_file=None, rrules=None):
    

        self.CoreIRNodes = CoreIRNodes
        self.ArchNodes = ArchNodes
        self.table = RewriteTable(CoreIRNodes, ArchNodes)
        self.num_pes = 0
        self.kernel_cycles = {}
        self.const_rr = None
        self.bit_const_rr = None        
        self.gen_rules(ops, rule_file, rrules)
        self.compile_time_rule_gen = lambda dag : None
        
        self.inst_sel = alg(self.table)

    def gen_rules(self, ops, rule_file=None, rrules=None):

        if rule_file is None and rrules is None:
            for node_name in self.ArchNodes._node_names:
                # auto discover the rules for CoreIR
                for op in ops:
                    peak_rule = self.table.discover(op, node_name)
                    print(f"Searching for {op} -> {node_name}")
                    if peak_rule is None:
                        print(f"  Not Found :(")
                        pass
                    else:
                        print(f"  Found!")
        else:
            for ind, peak_rule in enumerate(rrules):
                if ops != None:
                    op = ops[ind]
                    if "fp" in op and "pipelined" in op:
                        op = op.split("_pipelined")[0]
                    # if op == 'const' or op == 'const_pipelined':
                    #     self.const_rr = peak_rule
                    # elif op == 'bit_const' or op == 'bit_const_pipelined':
                    #     self.bit_const_rr = peak_rule
                    # else:
                    self.table.add_peak_rule(peak_rule, op)
                else:
                    self.table.add_peak_rule(peak_rule, None)
            self.table.sort_rules()

    def do_mapping(self, dag, kname="", convert_unbound=True, prove_mapping=True, node_cycles=None, pe_reg_info=None) -> coreir.Module:
        self.compile_time_rule_gen(dag)
        original_dag = Clone().clone(dag, iname_prefix=f"original_")
        CustomInline(self.CoreIRNodes.custom_inline).run(dag)
        mapped_dag = self.inst_sel(dag)

        # if pe_reg_info is not None:
        #     ConstantPacking(pe_reg_info).run(mapped_dag)

        # if self.const_rr is not None:
        #     self.table.add_peak_rule(self.const_rr, "const")
        # if self.bit_const_rr is not None:
        #     self.table.add_peak_rule(self.bit_const_rr, "bit_const")


        # mapped_dag = self.inst_sel(mapped_dag)

        SimplifyCombines().run(mapped_dag)
        RemoveSelects().run(mapped_dag)

        self.num_pes += count_pes(mapped_dag)
        print(count_pes(mapped_dag))
        unmapped = VerifyNodes(self.ArchNodes).verify(mapped_dag)
        
        if unmapped is not None:
            raise ValueError(f"Following nodes were unmapped: {unmapped}")
        assert VerifyNodes(self.CoreIRNodes).verify(original_dag) is None

        if node_cycles is not None:
            DelayMatching(node_cycles).run(mapped_dag)
            self.kernel_cycles[kname] = KernelDelay(node_cycles).doit(mapped_dag)

        if prove_mapping:
            counter_example = prove_equal(original_dag, mapped_dag)
            if counter_example is not None:
                raise ValueError(f"Mapped is not the same {counter_example}")
        #Create a new module representing the mapped_dag

        if convert_unbound:
            Unbound2Const().run(mapped_dag)
        return mapped_dag
