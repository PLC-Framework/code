"""BlockInterface — how an FB or an FC is called."""
from dataclasses import dataclass, field
from typing import Any, Optional

from .parameter import Parameter


@dataclass(slots=True)
class BlockInterface:
    """The call interface of an FB or FC: the parameters of each section, in the
    order the block declares them, and an FC's return type.

    Each parameter carries its type as well as its name. Names alone were the
    first shape (2026-09-25), on the reasoning that TIA takes a parameter's type
    from the block being called; the VM said otherwise - a LAD call whose
    <Parameter> has no Type is refused on import (2026-09-30) - and a template
    that only names a core function has to write the whole call out of this.

    Only the top level of VAR_INPUT, VAR_OUTPUT and VAR_IN_OUT: a parameter
    declared Struct is one parameter to a caller. A UDT, a constant table, or a
    source whose interface could not be read carries None on its node instead.
    """

    input: list[Parameter] = field(default_factory=list)      # VAR_INPUT, in declaration order
    output: list[Parameter] = field(default_factory=list)     # VAR_OUTPUT, in declaration order
    inout: list[Parameter] = field(default_factory=list)      # VAR_IN_OUT, in declaration order
    returns: Optional[str] = None                              # an FC's return type as written ("Int", "Void"); None on an FB

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BlockInterface":
        return cls(
            input=[Parameter.from_json(x) for x in data["input"]],
            output=[Parameter.from_json(x) for x in data["output"]],
            inout=[Parameter.from_json(x) for x in data["inout"]],
            returns=data["return"],
        )

    def to_json(self) -> dict[str, Any]:
        # "return" is the key the file carries; it is a Python keyword, hence
        # the attribute's other name.
        return {
            "input": [p.to_json() for p in self.input],
            "output": [p.to_json() for p in self.output],
            "inout": [p.to_json() for p in self.inout],
            "return": self.returns,
        }
