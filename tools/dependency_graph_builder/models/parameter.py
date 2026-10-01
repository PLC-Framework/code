"""Parameter — one entry of a call interface."""
from dataclasses import dataclass
from typing import Any, Optional, Union


@dataclass(slots=True)
class Parameter:
    """One parameter of an FB's or FC's call interface: its name, and its type as the
    source declares it.

    The type is written exactly as it stands after the colon, without an initial
    value or the closing semicolon: "Bool", "Time", "Array[0..9] of Byte", and a
    PLC data type in its quotes, '"delayOnOff"'. That is TIA's own spelling, since
    the core's sources are TIA's own exports, and it is the spelling SimaticML
    wants in a call's <Parameter Type="..."> - which a call cannot do without:
    TIA refuses to import one that leaves it out (measured on the VM, 2026-09-30).
    A parameter declared Struct is "Struct"; its members are not listed.

    None means the type is not known, which is what every parameter of a
    core.json written before types were recorded reads back as.
    """

    name: str
    type: Optional[str] = None

    @classmethod
    def from_json(cls, data: Union[str, dict[str, Any]]) -> "Parameter":
        # A core.json written before 2026-09-30 lists names alone.
        if isinstance(data, str):
            return cls(name=data)
        return cls(name=data["name"], type=data.get("type"))

    def to_json(self) -> dict[str, Any]:
        return {"name": self.name, "type": self.type}
