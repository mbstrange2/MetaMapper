from peak.ir import IR
from hwtypes import BitVector, Bit
from hwtypes.adt import Product
from peak import Peak, name_outputs, family_closure, Const
from peak.family import AbstractFamily, MagmaFamily, SMTFamily
from ...node import Nodes, Constant, DagNode, Select
from hwtypes import SMTFPVector, FPVector, RoundingMode
import magma

def gen_custom_ops_peak_CoreIR(width):
    CoreIR = IR()
    DATAWIDTH = 16
    def BFloat16_fc(family):
        if isinstance(family, MagmaFamily):
            BFloat16 =  magma.BFloat[16]
            BFloat16.reinterpret_from_bv = lambda bv: BFloat16(bv)
            BFloat16.reinterpret_as_bv = lambda f: magma.Bits[16](f)
            return BFloat16
        elif isinstance(family, SMTFamily):
            FPV = SMTFPVector
        else:
            FPV = FPVector
        BFloat16 = FPV[8, 7, RoundingMode.RNE, False]
        return BFloat16

    @family_closure
    def fp_getffrac_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_getffrac(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                signa = BitVector[16]((in0 & 0x8000))
                manta = BitVector[16]((in0 & 0x7F)) | 0x80
                expa0 = BitVector[8](in0[7:15])
                biased_exp0 = SInt[9](expa0.zext(1))
                unbiased_exp0 = SInt[9](biased_exp0 - SInt[9](127))

                if (unbiased_exp0 < 0):
                    manta_shift1 = BitVector[16](
                        manta) >> BitVector[16](-unbiased_exp0)
                else:
                    manta_shift1 = BitVector[16](
                        manta) << BitVector[16](unbiased_exp0)
                unsigned_res = BitVector[16]((manta_shift1 & 0x07F))
                if (signa == 0x8000):
                    signed_res = -SInt[16](unsigned_res)
                else:
                    signed_res = SInt[16](unsigned_res)

                # We are not checking for overflow when converting to int
                res = signed_res
                return res
        return fp_getffrac
    CoreIR.add_instruction("fp_getffrac", fp_getffrac_fc)


    @family_closure
    def fp_getfint_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_getfint(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                signa = BitVector[16]((in0 & 0x8000))
                manta = BitVector[16]((in0 & 0x7F)) | 0x80
                expa0 = UInt(in0)[7:15]
                biased_exp0 = SInt[9](expa0.zext(1))
                unbiased_exp0 = SInt[9](biased_exp0 - SInt[9](127))
                if (unbiased_exp0 < 0):
                    manta_shift0 = BitVector[23](0)
                else:
                    manta_shift0 = BitVector[23](
                        manta) << BitVector[23](unbiased_exp0)
                unsigned_res0 = BitVector[23](manta_shift0 >> BitVector[23](7))
                unsigned_res = BitVector[16](unsigned_res0[0:16])
                if (signa == 0x8000):
                    signed_res = -SInt[16](unsigned_res)
                else:
                    signed_res = SInt[16](unsigned_res)
                # We are not checking for overflow when converting to int
                res = signed_res
                return res
        return fp_getfint
    
    CoreIR.add_instruction("fp_getfint", fp_getfint_fc)

    @family_closure
    def fp_cnvint2f_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_cnvint2f(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                sign = BitVector[16](0)
                if (sign[15] == Bit(1)):
                    abs_input = BitVector[16](-SInt[16](in0))
                else:
                    abs_input = BitVector[16](in0)
                scale = SInt[16](-127)
                # for bit_pos in range(8):
                #   if (abs_exp[bit_pos]==Bit(1)):
                #     scale = bit_pos
                if (abs_input[0] == Bit(1)):
                    scale = SInt[16](0)
                if (abs_input[1] == Bit(1)):
                    scale = SInt[16](1)
                if (abs_input[2] == Bit(1)):
                    scale = SInt[16](2)
                if (abs_input[3] == Bit(1)):
                    scale = SInt[16](3)
                if (abs_input[4] == Bit(1)):
                    scale = SInt[16](4)
                if (abs_input[5] == Bit(1)):
                    scale = SInt[16](5)
                if (abs_input[6] == Bit(1)):
                    scale = SInt[16](6)
                if (abs_input[7] == Bit(1)):
                    scale = SInt[16](7)
                if (abs_input[8] == Bit(1)):
                    scale = SInt[16](8)
                if (abs_input[9] == Bit(1)):
                    scale = SInt[16](9)
                if (abs_input[10] == Bit(1)):
                    scale = SInt[16](10)
                if (abs_input[11] == Bit(1)):
                    scale = SInt[16](11)
                if (abs_input[12] == Bit(1)):
                    scale = SInt[16](12)
                if (abs_input[13] == Bit(1)):
                    scale = SInt[16](13)
                if (abs_input[14] == Bit(1)):
                    scale = SInt[16](14)
                if (abs_input[15] == Bit(1)):
                    scale = SInt[16](15)
                normmant_mul_left = SInt[16](abs_input)
                normmant_mul_right = (SInt[16](15)-scale)
                normmant_mask = SInt[16](0x7f00)

                #if (alu == ALU_t.FCnvInt2F) | (alu == ALU_t.FCnvExp2F):
                if (scale >= 0):
                    normmant = BitVector[16](
                        (normmant_mul_left << normmant_mul_right) & normmant_mask)
                else:
                    normmant = BitVector[16](0)

                
                normmant = BitVector[16](normmant) >> 8

                biased_scale = scale + 127
                to_float_DW_result = (sign | ((BitVector[16](biased_scale) << 7) & (
                        0xFF << 7)) | normmant)

                return to_float_DW_result
        return fp_cnvint2f
    CoreIR.add_instruction("fp_cnvint2f", fp_cnvint2f_fc)

    @family_closure
    def fp_cnvexp2f_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_cnvexp2f(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                expa0 = BitVector[8](in0[7:15])
                biased_exp0 = SInt[9](expa0.zext(1))
                unbiased_exp0 = SInt[9](biased_exp0 - SInt[9](127))
                if (unbiased_exp0 < 0):
                    sign = BitVector[16](0x8000)
                    abs_exp0 = -unbiased_exp0
                else:
                    sign = BitVector[16](0x0000)
                    abs_exp0 = unbiased_exp0
                abs_exp = BitVector[8](abs_exp0[0:8])
                scale = SInt[16](-127)
                # for bit_pos in range(8):
                #   if (abs_exp[bit_pos]==Bit(1)):
                #     scale = bit_pos
                if (abs_exp[0] == Bit(1)):
                    scale = SInt[16](0)
                if (abs_exp[1] == Bit(1)):
                    scale = SInt[16](1)
                if (abs_exp[2] == Bit(1)):
                    scale = SInt[16](2)
                if (abs_exp[3] == Bit(1)):
                    scale = SInt[16](3)
                if (abs_exp[4] == Bit(1)):
                    scale = SInt[16](4)
                if (abs_exp[5] == Bit(1)):
                    scale = SInt[16](5)
                if (abs_exp[6] == Bit(1)):
                    scale = SInt[16](6)
                if (abs_exp[7] == Bit(1)):
                    scale = SInt[16](7)
                normmant_mul_left = SInt[16](abs_exp)
                normmant_mul_right = (SInt[16](7)-scale)
                normmant_mask = SInt[16](0x7F)

                if (scale >= 0):
                    normmant = BitVector[16](
                        (normmant_mul_left << normmant_mul_right) & normmant_mask)
                else:
                    normmant = BitVector[16](0)

                biased_scale = scale + 127
                to_float_DW_result = (sign | ((BitVector[16](biased_scale) << 7) & (
                        0xFF << 7)) | normmant)
                return to_float_DW_result
        return fp_cnvexp2f

    CoreIR.add_instruction("fp_cnvexp2f", fp_cnvexp2f_fc)

    @family_closure
    def fp_subexp_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_subexp(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                signa = BitVector[16]((in0 & 0x8000))
                expa = UInt(in0)[7:15]
                signb = BitVector[16]((in1 & 0x8000))
                expb = UInt(in1)[7:15]
                expa = (expa - expb + 127)
                exp_shift = BitVector[16](expa)
                exp_shift = exp_shift << 7
                manta = BitVector[16]((in0 & 0x7F))
                res = ((signa | signb) | exp_shift | manta)
                return res
        return fp_subexp

    CoreIR.add_instruction("fp_subexp", fp_subexp_fc)


    @family_closure
    def fp_addiexp_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]
        BitVector = family.BitVector

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_addiexp(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                sign = BitVector[16]((in0 & 0x8000))
                exp = UInt(in0)[7:15]
                exp_check = exp.zext(1)
                exp = exp + UInt(in1)[0:8]
                exp_check = exp_check + UInt(in1)[0:9]
                # Augassign not supported by magma yet
                # exp += SInt[8](in1[0:8])
                # exp_check += SInt[9](in1[0:9])
                exp_shift = BitVector[16](exp)
                exp_shift = exp_shift << 7
                mant = BitVector[16]((in0 & 0x7F))
                res = (sign | exp_shift | mant)
                return res
        
        return fp_addiexp
    
    CoreIR.add_instruction("fp_addiexp", fp_addiexp_fc)


    @family_closure
    def fp_getmant_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        @family.assemble(locals(), globals())
        class fp_getmant(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                return Data(in0 & 0x7F)
        return fp_getmant

    CoreIR.add_instruction("fp_getmant", fp_getmant_fc)


    @family_closure
    def fp_mux_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        @family.assemble(locals(), globals())
        class fp_mux(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data, sel:Bit) -> Data:
                return sel.ite(in0, in1)
        return fp_mux

    CoreIR.add_instruction("float.mux", fp_mux_fc)


    @family_closure
    def fp_add_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_add(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(float_DW2bv(a_fpadd + b_fpadd))
        
        return fp_add

    CoreIR.add_instruction("float_DW.fp_add", fp_add_fc)


    @family_closure
    def fp_gt_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_gt(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Bit:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Bit(a_fpadd > b_fpadd)
        
        return fp_gt

    CoreIR.add_instruction("fp_gt", fp_gt_fc)


    @family_closure
    def fp_lt_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_lt(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Bit:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Bit(a_fpadd < b_fpadd)
        
        return fp_lt

    CoreIR.add_instruction("fp_lt", fp_lt_fc)


    @family_closure
    def fp_exp_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_exp(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                return a_fpadd
        
        return fp_exp

    CoreIR.add_instruction("float.exp", fp_exp_fc)



    @family_closure
    def fp_sub_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_sub(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(float_DW2bv(a_fpadd - b_fpadd))
        
        return fp_sub
    
    CoreIR.add_instruction("float.sub", fp_sub_fc)


    @family_closure
    def fp_mul_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_mul(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(float_DW2bv(a_fpadd - b_fpadd))
        
        return fp_mul
    
    CoreIR.add_instruction("float_DW.fp_mul", fp_mul_fc)


    @family_closure
    def fp_div_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_div(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(float_DW2bv(a_fpadd - b_fpadd))
        
        return fp_div
    
    CoreIR.add_instruction("float.div", fp_div_fc)

    @family_closure
    def fp_max_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_max(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(float_DW2bv(a_fpadd - b_fpadd))
        
        return fp_max
    
    CoreIR.add_instruction("float.max", fp_max_fc)

    @family_closure
    def fp_min_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_min(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0 : Data, in1 : Data) -> Data:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                return Data(a_fpadd - b_fpadd)
        
        return fp_min
    
    CoreIR.add_instruction("float.min", fp_min_fc)



    @family_closure
    def fp_cmp_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Unsigned[32]
        SInt = family.Signed[16]
        UInt = family.Unsigned[16]
        Bit = family.Bit

        BFloat16 = BFloat16_fc(family)
        FPExpBV = family.BitVector[8]
        FPFracBV = family.BitVector[7]

        def bv2float_DW(bv):
            return BFloat16.reinterpret_from_bv(bv)

        def float_DW2bv(bvf):
            return BFloat16.reinterpret_as_bv(bvf)

        def fp_get_exp(val : Data):
            return val[7:15]

        def fp_get_frac(val : Data):
            return val[:7]

        def fp_is_zero(val : Data):
            return (fp_get_exp(val) == FPExpBV(0)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_inf(val : Data):
            return (fp_get_exp(val) == FPExpBV(-1)) & (fp_get_frac(val) == FPFracBV(0))

        def fp_is_neg(val : Data):
            return Bit(val[-1])

        @family.assemble(locals(), globals())
        class fp_cmp(Peak):
            @name_outputs(out=Bit)
            def __call__(self, in0 : Data, in1 : Data) -> Bit:
                
                a_fpadd = bv2float_DW(in0)
                b_fpadd = bv2float_DW(in1)
                a_inf = fp_is_inf(in0)
                b_inf = fp_is_inf(in1)
                a_neg = fp_is_neg(in0)
                b_neg = fp_is_neg(in1)

                res = Data(float_DW2bv(a_fpadd - b_fpadd))
                Z = fp_is_zero(res)
                if (a_inf & b_inf) & (a_neg == b_neg):
                    Z = Bit(1)

                return Z
    
        return fp_cmp
    
    CoreIR.add_instruction("float_DW.cmp", fp_cmp_fc)

    @family_closure
    def mult_middle_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.BitVector[32]
        class mult_middle(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0: Data, in1: Data) -> Data:
                mul = Data32(in0) * Data32(in1)
                res = mul >> 8
                return Data(res[0:16])
        return mult_middle

    CoreIR.add_instruction("commonlib.mult_middle", mult_middle_fc)


    @family_closure
    def sext_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.BitVector[32]
        class sext(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0: Data) -> Data32:
                res = Data32(in0)
                return res
        return sext

    CoreIR.add_instruction("coreir.sext", sext_fc)

    @family_closure
    def slice_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.BitVector[32]
        class slice(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0: Data32) -> Data:
                res = Data(in0[8:24])
                return res
        return slice

    CoreIR.add_instruction("coreir.slice", slice_fc)

    @family_closure
    def mul32_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.BitVector[32]
        class mul32(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0: Data32, in1: Data32) -> Data32:
                res = Data32(in0) * Data32(in1)
                return Data32(res)
        return mul32

    CoreIR.add_instruction("coreir.mul32", mul32_fc)


    @family_closure
    def ashr32_fc(family: AbstractFamily):
        Data = family.BitVector[16]
        Data32 = family.Signed[32]
        class ashr32(Peak):
            @name_outputs(out=Data)
            def __call__(self, in0: Data32, in1: Data32) -> Data32:
                res = Data32(in0) >> Data32(in1)
                return Data32(res)
        return ashr32

    CoreIR.add_instruction("coreir.ashr32", ashr32_fc)

    return CoreIR
