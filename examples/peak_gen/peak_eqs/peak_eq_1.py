
from peak import Peak, family_closure, Const
from peak import family
from peak.family import AbstractFamily

@family_closure
def mapping_function_1_fc(family: AbstractFamily):
    Data = family.BitVector[16]
    SData = family.Signed[16]
    Bit = family.Bit
    @family.assemble(locals(), globals())
    class mapping_function_1(Peak):
        def __call__(self, in0 : Data, in1 : Data) -> Data:
            sub = SData(in0 - in1)
            return Data(sub) if (sub >= SData(0)) else (SData(-1)*sub)
      
    return mapping_function_1
