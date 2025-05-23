from .ir import gen_peak_CoreIR
from ...node import Nodes, Constant, DagNode, Select, Dag, Input, Output
from ... import CoreIRContext
from ...peak_util import load_from_peak, peak_to_coreir
from ...common_passes import print_dag, Clone
import coreir
from hwtypes import BitVector, Product, strip_modifiers, Bit
from peak import family
import struct
import math
import os

def strip_trailing(op):
    if op[-1] == "_":
        return op[:-1]
    return op

def gen_CoreIRNodes(width):
    CoreIRNodes = Nodes("CoreIR")
    peak_ir = gen_peak_CoreIR(width)
    c = CoreIRContext()
    cgralib = True
    try:
        c.load_library("cgralib")
    except:
        cgralib = False

    basic = ("mul", "add", "const", "and_", "or_", "neg")
    other = ("ashr", "eq", "neq", "lshr", "mux", "sub", "slt", "sle", "sgt", "sge", "ult", "ule", "ugt", "uge", "shl")
    bit_ops = ("const", "or_", "and_", "xor", "not_", "mux")
    commonlib_ops = ("abs", "smax", "smin", "umin", "umax")
    for namespace, ops, is_module in (
        ("corebit", bit_ops, True),
        ("coreir", basic + other, False)
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
            modparams = ()
            if op == "const":
                modparams = ("value",)
            name_ = load_from_peak(CoreIRNodes, peak_fc, cmod=cmod, name=name, modparams=modparams)
            assert name_ == name
            assert name in CoreIRNodes.coreir_modules
            assert CoreIRNodes.name_from_coreir(cmod) == name

    CoreIRNodes.custom_nodes = ["coreir.neq", "commonlib.abs", "commonlib.mult_middle", # ALU ops
                                "float.eq", "float.gt", "float.le", "float.ge", "float.lt", # FP instruction
                                "float.max", "float.min", "float.div", "float_DW.fp_mul",
                                "float_DW.fp_add", "float.sub", "float.exp", "float.mux",
                                "float.ln", "float.abs_max", "float.bit8_unpack_high",
                                "float.bit8_unpack_low", "float.bit8_pack", "float.get_shared_exp", "float.e8m0_quant",
                                "fp_getmant", "fp_addiexp", "fp_subexp", "fp_cnvexp2f", "fp_getfint", # FPU ops
                                "fp_getffrac", "fp_cnvint2f", "bit8_unpack_high", "bit8_unpack_low", "bit8_pack",
                                "get_shared_exp", "e8m0_quant"]

    for name in CoreIRNodes.custom_nodes:
        if name not in CoreIRNodes.coreir_modules:
            peak_fc = peak_ir.instructions[name]
            cmod = None
            name_ = load_from_peak(CoreIRNodes, peak_fc, cmod=cmod, name=name, modparams=())

    if cgralib:
        name = f"cgralib.Mem"
        peak_fc = peak_ir.instructions[name]
        cmod = c.get_namespace('cgralib').generators['Mem'](ctrl_width=16, has_chain_en=False, has_external_addrgen=False, has_flush=True, has_read_valid=False, has_reset=False, has_stencil_valid=True, has_valid=False, is_rom=True, num_inputs=2, num_outputs=2, use_prebuilt_mem=True, width=16)
        name_ = load_from_peak(CoreIRNodes, peak_fc, cmod=cmod, stateful=True, name="cgralib.Mem", modparams=())

        name = f"cgralib.Pond"
        peak_fc = peak_ir.instructions[name]
        cmod = c.get_namespace('cgralib').generators['Pond'](num_inputs=2, num_outputs=2, width=16)
        name_ = load_from_peak(CoreIRNodes, peak_fc, cmod=cmod, stateful=True, name="cgralib.Pond", modparams=())



    class Mem_amber(DagNode):
        def __init__(self, clk_en, data_in_0, data_in_1, wen_in_0, wen_in_1, *, iname):
            super().__init__(clk_en, data_in_0, data_in_1, wen_in_0, wen_in_1, iname=iname)
            self.modparams=()
        @property
        def attributes(self):
            return ("iname")

        nodes = CoreIRNodes
        static_attributes = {}
        node_name = "cgralib.Mem_amber"
        num_children = 3
        type = Product.from_fields("Output",{"data_out_0":BitVector[16], "data_out_1":BitVector[16], "stencil_valid":BitVector[1]})

    # Detect whether in RV or static HW
    dense_ready_valid = "DENSE_READY_VALID" in os.environ and os.environ.get("DENSE_READY_VALID") == "1"
    if dense_ready_valid:
        # We don't need the const PE to feed 1b rd_en constant
        class FPRom(DagNode):
            def __init__(self, raddr, *, init, iname):
                super().__init__(raddr, init=init, iname=iname)
                self.modparams=()
            @property
            def attributes(self):
                return ("init", "iname")

            #Hack to get correct port name
            def select(self, field, original=None):
                self._selects.add("rdata")
                return Select(self, field="rdata",type=BitVector[16])

            nodes = CoreIRNodes
            static_attributes = {}
            node_name = "memory.fprom2"
            num_children = 1
            type = Product.from_fields("Output",{"rdata":BitVector[16]})
    else:
        class FPRom(DagNode):
            def __init__(self, raddr, ren, *, init, iname):
                super().__init__(raddr, ren, init=init, iname=iname)
                self.modparams=()
            @property
            def attributes(self):
                return ("init", "iname")

            #Hack to get correct port name
            def select(self, field, original=None):
                self._selects.add("rdata")
                return Select(self, field="rdata",type=BitVector[16])

            nodes = CoreIRNodes
            static_attributes = {}
            node_name = "memory.fprom2"
            num_children = 2
            type = Product.from_fields("Output",{"rdata":BitVector[16]})


    def float2bfbin(fnum):
       if (fnum=='NaN'):
         sign = '0'
         exp  = '11111111'
         lfrac = '11111111'
       elif (fnum=='-NaN'):
         sign = '1'
         exp  = '11111111'
         lfrac = '11111111'
       elif (fnum=='Inf'):
         sign = '0'
         exp  = '11111111'
         lfrac = '00000000'
       elif (fnum=='-Inf'):
         sign = '1'
         exp  = '11111111'
         lfrac = '00000000'
       else:
         fstr  = ''.join("{:08b}".format(elem) for elem in struct.pack('!f', fnum))
         sign  = fstr[0]
         exp   = fstr[1:9]
         lfrac = "0"+fstr[9:16]
         hfrac = fstr[16:]
         #Enable rounding
         if (hfrac[0]=="1"): #bit 8 of the float mantissa is set, so round up
           if (lfrac[1:8]=="1111111"): #roll over mantissa and increase exp if needed
             exp = "{:08b}".format((int(exp,2) + 1)) #exp overflow?
           lfrac = "{:08b}".format((int(lfrac,2) + 1))

       return sign + exp + lfrac[1:8]

    ######### Definition of float.div #########
    def div_lut(index):
        x = (1.0 + float(int(index))/128.0)
        x_inv = 1.0/x
        return int(float2bfbin(x_inv),2)
    depth = 1024
    div_rom_init = [div_lut(i) for i in range(0, 128)]+[0x0000]*(depth - 128)

    rom2 = CoreIRContext().get_namespace("memory").generators["rom2"](depth=256, width=width)
    CoreIRNodes.add("memory.fprom2", peak_ir.instructions["memory.rom2"], rom2, FPRom)

    input_t = Product.from_fields("Input", {f"in{i}": BitVector[16] for i in range(2)})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node = Input(iname="self", type=input_t)
    in0 = source_node.select("in0")
    in1 = source_node.select("in1")
    get_mant = CoreIRNodes.dag_nodes["fp_getmant"](in1,Constant(value=BitVector[16](0), type=BitVector[16]))

    en_const = Constant(value=Bit(1), type=Bit)
    en_const_dag = CoreIRNodes.dag_nodes["corebit.const"](en_const)

    if dense_ready_valid:
        rom = FPRom(get_mant.select("out"), init=div_rom_init, iname="fpdivrom")
    else:
        rom = FPRom(get_mant.select("out"), en_const_dag.select("out"), init=div_rom_init, iname="fpdivrom")
    sub_exp = CoreIRNodes.dag_nodes["fp_subexp"](rom.select("rdata"), in1)
    mult = CoreIRNodes.dag_nodes["float_DW.fp_mul"](sub_exp.select("out"), in0)
    sink_node = Output(mult.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.div"] = (Dag(sources=[source_node], sinks=[sink_node]), [get_mant, sub_exp, mult])


    ######### Definition of float.exp #########
    def exp_lut(index):
        x = (0.0 + float(int(index))/128.0)
        return int(float2bfbin((2**x)),2)


    exp_rom_init = [exp_lut(i) for i in range(0, 128)]+[exp_lut(i) for i in range(-128, 0)]+[0x0000]*(depth - 256)

    input_t = Product.from_fields("Input", {"in0": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node1 = Input(iname="self", type=input_t)
    in0 = source_node1.select("in0")

    ln2_inv = 1.0/math.log(2)
    ln2_inv_bf = int(float2bfbin(ln2_inv), 2)
    const_ln2_inv = Constant(value=BitVector[16](ln2_inv_bf), type=BitVector[16])
    const_ln2_inv_dag = CoreIRNodes.dag_nodes["coreir.const"](const_ln2_inv)
    ln2_mult = CoreIRNodes.dag_nodes["float_DW.fp_mul"](const_ln2_inv_dag.select("out"), in0)

    get_int = CoreIRNodes.dag_nodes["fp_getfint"](ln2_mult.select("out"), Constant(value=BitVector[16](0), type=BitVector[16]))
    get_frac = CoreIRNodes.dag_nodes["fp_getffrac"](ln2_mult.select("out"), Constant(value=BitVector[16](0), type=BitVector[16]))



    en_const = Constant(value=Bit(1), type=Bit)
    en_const_dag = CoreIRNodes.dag_nodes["corebit.const"](en_const)

    # We added the masking to PE to reduce utilization
    # and_const = Constant(value=BitVector[16](255), type=BitVector[16])
    # and_const_dag = CoreIRNodes.dag_nodes["coreir.const"](and_const)
    # rom_idx = CoreIRNodes.dag_nodes["coreir.and_"](get_frac.select("out"), and_const_dag.select("out"))
    # rom = FPRom(rom_idx.select("out"), en_const_dag.select("out"), init=exp_rom_init, iname="fpexprom")

    if dense_ready_valid:
        rom = FPRom(get_frac.select("out"), init=exp_rom_init, iname="fpexprom")
    else:
        rom = FPRom(get_frac.select("out"), en_const_dag.select("out"), init=exp_rom_init, iname="fpexprom")

    add_exp = CoreIRNodes.dag_nodes["fp_addiexp"](rom.select("rdata"), get_int.select("out"))

    sink_node = Output(add_exp.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.exp"] = (Dag(sources=[source_node1], sinks=[sink_node]), [ln2_mult])

    ######### Definition of float.ln #########
    def ln_lut(index):
        # index goes from 0..127, representing the fractional part in [1.0 .. 1.996...]
        fraction = 1.0 + float(index)/128.0
        return int(float2bfbin(math.log(fraction)), 2)
    depth = 1024
    ln_rom_init = [ln_lut(i) for i in range(128)] + [0x0000]*(depth - 128)

    rom_ln = CoreIRContext().get_namespace("memory").generators["rom2"](depth=256, width=width)
    CoreIRNodes.add("memory.fprom_ln", peak_ir.instructions["memory.rom2"], rom_ln, FPRom)

    input_t = Product.from_fields("Input", {"in0": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node = Input(iname="self", type=input_t)
    in0 = source_node.select("in0")

    get_mant = CoreIRNodes.dag_nodes["fp_getmant"](in0, Constant(value=BitVector[16](0), type=BitVector[16]))
    exp2float = CoreIRNodes.dag_nodes["fp_cnvexp2f"](in0, Constant(value=BitVector[16](0), type=BitVector[16]))

    ln2 = math.log(2)
    ln2_bf = int(float2bfbin(ln2), 2)
    ln2_const = Constant(value=BitVector[16](ln2_bf), type=BitVector[16])
    ln2_dag = CoreIRNodes.dag_nodes["coreir.const"](ln2_const)

    mul_ln2 = CoreIRNodes.dag_nodes["float_DW.fp_mul"](exp2float.select("out"), ln2_dag.select("out"))
    en_const = Constant(value=Bit(1), type=Bit)
    en_const_dag = CoreIRNodes.dag_nodes["corebit.const"](en_const)

    if dense_ready_valid:
        ln_rom = FPRom(get_mant.select("out"), init=ln_rom_init, iname="fplnrom")
    else:
        ln_rom = FPRom(get_mant.select("out"), en_const_dag.select("out"), init=ln_rom_init, iname="fplnrom")

    ln_add = CoreIRNodes.dag_nodes["float_DW.fp_add"](mul_ln2.select("out"), ln_rom.select("rdata"))

    sink_node = Output(ln_add.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.ln"] = (Dag(sources=[source_node], sinks=[sink_node]), [get_mant, exp2float, mul_ln2, ln_add])

    ######### Definition of float.min #########
    input_t = Product.from_fields("Input", {f"in{i}": BitVector[16] for i in range(2)})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node3 = Input(iname="self", type=input_t)
    in0 = source_node3.select("in0")
    in1 = source_node3.select("in1")

    lt = CoreIRNodes.dag_nodes["float.lt"](in0, in1)

    min_ = CoreIRNodes.dag_nodes["coreir.mux"](in1, in0, lt.select("out"))

    sink_node = Output(min_.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.min"] = (Dag(sources=[source_node3], sinks=[sink_node]), [lt, min_])

    ######### Definition of coreir.neq #########
    input_t = Product.from_fields("Input", {f"in{i}": BitVector[16] for i in range(2)})
    output_t = Product.from_fields("Output", {"out": Bit})

    source_node4 = Input(iname="self", type=input_t)
    in0 = source_node4.select("in0")
    in1 = source_node4.select("in1")

    eq = CoreIRNodes.dag_nodes["coreir.eq"](in0, in1)

    not_ = CoreIRNodes.dag_nodes["corebit.not_"](eq.select("out"))

    sink_node = Output(not_.select("out"), type=output_t)

    CoreIRNodes.custom_inline["coreir.neq"] = (Dag(sources=[source_node4], sinks=[sink_node]), [eq])

    ######### Definition of float.bit8_unpack_high #########
    input_t = Product.from_fields("Input", {"in0": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node_bit8_unpack_high = Input(iname="self", type=input_t)
    in0 = source_node_bit8_unpack_high.select("in0")

    high_unpack = CoreIRNodes.dag_nodes["bit8_unpack_high"](in0)
    sink_node = Output(high_unpack.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.bit8_unpack_high"] = (Dag(sources=[source_node_bit8_unpack_high], sinks=[sink_node]), [high_unpack])

    ######### Definition of float.bit8_unpack_low #########
    input_t = Product.from_fields("Input", {"in0": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node_bit8_unpack_low = Input(iname="self", type=input_t)
    in0 = source_node_bit8_unpack_low.select("in0")

    low_unpack = CoreIRNodes.dag_nodes["bit8_unpack_low"](in0)
    sink_node = Output(low_unpack.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.bit8_unpack_low"] = (Dag(sources=[source_node_bit8_unpack_low], sinks=[sink_node]), [low_unpack])

    ########### Definition of float.bit8_pack #########
    input_t = Product.from_fields("Input", {"in0": BitVector[16], "in1": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node_bit8_pack = Input(iname="self", type=input_t)
    in0 = source_node_bit8_pack.select("in0")
    in1 = source_node_bit8_pack.select("in1")

    bit8_pack = CoreIRNodes.dag_nodes["bit8_pack"](in0, in1, type=BitVector[16])
    sink_node = Output(bit8_pack.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.bit8_pack"] = (Dag(sources=[source_node_bit8_pack], sinks=[sink_node]), [bit8_pack])

    ######### Definition of float.get_shared_exp #########
    input_t = Product.from_fields("Input", {"in0": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node_get_shared_exp = Input(iname="self", type=input_t)
    in0 = source_node_get_shared_exp.select("in0")

    shared_exp = CoreIRNodes.dag_nodes["get_shared_exp"](in0)
    sink_node = Output(shared_exp.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.get_shared_exp"] = (Dag(sources=[source_node_get_shared_exp], sinks=[sink_node]), [shared_exp])

    ######### Definition of float.e8m0_quant #########
    input_t = Product.from_fields("Input", {"in0": BitVector[16], "in1": BitVector[16]})
    output_t = Product.from_fields("Output", {"out": BitVector[16]})

    source_node_e8m0_quant = Input(iname="self", type=input_t)
    in0 = source_node_e8m0_quant.select("in0")
    in1 = source_node_e8m0_quant.select("in1")

    e8m0_quantization = CoreIRNodes.dag_nodes["e8m0_quant"](in0, in1, type=BitVector[16])
    sink_node = Output(e8m0_quantization.select("out"), type=output_t)

    CoreIRNodes.custom_inline["float.e8m0_quant"] = (Dag(sources=[source_node_e8m0_quant], sinks=[sink_node]), [e8m0_quantization])

    return CoreIRNodes


