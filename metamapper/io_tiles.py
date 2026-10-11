


from metamapper.data_width import data_width
from hwtypes import BitVector
from peak import family, family_closure, Peak, name_outputs, Const

@family_closure
def IO_fc(family):
    BV = family.BitVector
    Bit = family.Bit
    width = data_width()

    @family.assemble(locals(), globals())
    class IO(Peak):
        @name_outputs(out=BV[width])
        def __call__(self, in_: BV[width]) -> (BV[width]):
            return in_

    return IO

@family_closure
def BitIO_fc(family):
    BV = family.BitVector
    Bit = family.Bit

    @family.assemble(locals(), globals())
    class BitIO(Peak):
        @name_outputs(out=Bit)
        def __call__(self, in_: Bit) -> (Bit):
            return in_

    return BitIO

