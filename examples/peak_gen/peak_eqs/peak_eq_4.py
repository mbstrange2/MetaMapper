
from peak import Peak, family_closure, Const
from peak import family
from peak.family import AbstractFamily

@family_closure
def mapping_function_4_fc(family: AbstractFamily):
    Data = family.BitVector[16]
    SData = family.Signed[16]
    Bit = family.Bit
    @family.assemble(locals(), globals())
    class mapping_function_4(Peak):
        def __call__(self, in0 : Data, in1 : Data) -> Bit:
  
            return (Bit(1) if in0 == in1 else Bit(0))
      
    return mapping_function_4
