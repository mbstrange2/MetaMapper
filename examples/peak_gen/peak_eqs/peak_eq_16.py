
from peak import Peak, family_closure, Const
from peak import family
from peak.family import AbstractFamily

@family_closure
def mapping_function_16_fc(family: AbstractFamily):
    Data = family.BitVector[16]
    SData = family.Signed[16]
    Bit = family.Bit
    @family.assemble(locals(), globals())
    class mapping_function_16(Peak):
        def __call__(self, in0 : Data, in1 : Data) -> Bit:
  
            return (Bit(1) if SData(in0) < SData(in1) else Bit(0))
      
    return mapping_function_16
