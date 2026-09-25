"""BlockInterface — how an FB or an FC is called."""
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(slots=True)
class BlockInterface:
    """The call interface of an FB or FC: the parameter names of each section,
    in the order the block declares them, and an FC's return type.

    Names only, on purpose: writing a call needs a parameter's name and which
    section it belongs to (`:=` for an input or an in-out, `=>` for an output),
    and TIA takes each parameter's type from the block being called. A UDT, a
    constant table, or a source whose interface could not be read carries None
    on its node instead.
    """

    input: list[str] = field(default_factory=list)      # VAR_INPUT, in declaration order
    output: list[str] = field(default_factory=list)     # VAR_OUTPUT, in declaration order
    inout: list[str] = field(default_factory=list)      # VAR_IN_OUT, in declaration order
    returns: Optional[str] = None                        # an FC's return type as written ("Int", "Void"); None on an FB

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "BlockInterface":
        return cls(
            input=list(data["input"]),
            output=list(data["output"]),
            inout=list(data["inout"]),
            returns=data["return"],
        )

    def to_json(self) -> dict[str, Any]:
        # "return" is the key the file carries; it is a Python keyword, hence
        # the attribute's other name.
        return {
            "input": self.input,
            "output": self.output,
            "inout": self.inout,
            "return": self.returns,
        }
