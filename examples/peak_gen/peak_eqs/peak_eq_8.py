
from peak import Peak, family_closure, Const
from peak import family
from peak.family import AbstractFamily

@family_closure
def mapping_function_8_fc(family: AbstractFamily):
    Data = family.BitVector[16]
    SData = family.Signed[16]
    Bit = family.Bit
    @family.assemble(locals(), globals())
    class mapping_function_8(Peak):
        def __call__(self, in0 : Data, in1 : Data) -> Data:
  
            return (in0 if in0 > in1 else in1)
      
    return mapping_function_8
