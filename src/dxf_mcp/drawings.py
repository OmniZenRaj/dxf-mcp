"""Reading DXF drawings.

Kept free of MCP imports so it can be tested directly and reused. Every function
here is read-only; nothing in this package writes a drawing back.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import ezdxf
from ezdxf.document import Drawing

# DXF stores units as an integer code in $INSUNITS. Only the ones that turn up in
# practice are named; anything else is reported as its raw code rather than guessed at.
_UNITS = {
    0: "unitless", 1: "inches", 2: "feet", 4: "millimeters",
    5: "centimeters", 6: "meters", 9: "microinches", 10: "mils",
}


@dataclass
class LayerInfo:
    name: str
    color: int
    linetype: str
    is_on: bool
    is_locked: bool
    entity_count: int


@dataclass
class DrawingSummary:
    path: str
    dxf_version: str
    units: str
    layer_count: int
    block_definition_count: int
    entity_count: int
    entity_types: dict[str, int]
    layers_in_use: list[str]


@dataclass
class BomRow:
    """One block insertion, with its attributes flattened into a row."""
    block: str
    layer: str
    attributes: dict[str, str]


@dataclass
class BillOfMaterials:
    path: str
    row_count: int
    attribute_columns: list[str]
    rows: list[BomRow] = field(default_factory=list)


@dataclass
class StandardsFinding:
    rule: str
    severity: str
    detail: str


@dataclass
class StandardsReport:
    path: str
    passed: bool
    findings: list[StandardsFinding] = field(default_factory=list)


def load(path: Path) -> Drawing:
    """Open a DXF file, or raise a message worth showing a user."""
    try:
        return ezdxf.readfile(str(path))
    except IOError as exc:
        raise ValueError(f"Cannot read {path.name}: {exc}") from exc
    except ezdxf.DXFStructureError as exc:
        raise ValueError(f"{path.name} is not a valid DXF file: {exc}") from exc


def summarize(path: Path) -> DrawingSummary:
    doc = load(path)
    msp = doc.modelspace()

    types = Counter(e.dxftype() for e in msp)
    used = sorted({e.dxf.layer for e in msp if e.dxf.hasattr("layer")})
    units_code = doc.header.get("$INSUNITS", 0)

    return DrawingSummary(
        path=str(path),
        dxf_version=doc.dxfversion,
        units=_UNITS.get(units_code, f"code {units_code}"),
        layer_count=len(doc.layers),
        # Layout blocks (*Model_Space, *Paper_Space) are bookkeeping, not content.
        block_definition_count=sum(1 for b in doc.blocks if not b.name.startswith("*")),
        entity_count=sum(types.values()),
        entity_types=dict(sorted(types.items(), key=lambda kv: (-kv[1], kv[0]))),
        layers_in_use=used,
    )


def layers(path: Path) -> list[LayerInfo]:
    doc = load(path)
    counts = Counter(e.dxf.layer for e in doc.modelspace() if e.dxf.hasattr("layer"))
    return [
        LayerInfo(
            name=layer.dxf.name,
            color=layer.dxf.color,
            linetype=layer.dxf.linetype,
            is_on=layer.is_on(),
            is_locked=layer.is_locked(),
            entity_count=counts.get(layer.dxf.name, 0),
        )
        for layer in doc.layers
    ]


def bill_of_materials(path: Path, block: str | None = None) -> BillOfMaterials:
    """Flatten block insertions and their attributes into tabular rows.

    This is the shape a drawing has to be in before it can reach an ERP: one row
    per placed component, with the title-block and part attributes as columns.
    """
    doc = load(path)
    wanted = block.upper() if block else None

    rows: list[BomRow] = []
    columns: set[str] = set()

    for insert in doc.modelspace().query("INSERT"):
        name = insert.dxf.name
        if wanted and name.upper() != wanted:
            continue
        attrs = {a.dxf.tag: a.dxf.text for a in insert.attribs}
        columns.update(attrs)
        rows.append(BomRow(block=name, layer=insert.dxf.layer, attributes=attrs))

    return BillOfMaterials(
        path=str(path),
        row_count=len(rows),
        attribute_columns=sorted(columns),
        rows=rows,
    )


def check_standards(
    path: Path,
    required_layers: list[str] | None = None,
    forbidden_layers: list[str] | None = None,
    require_units: str | None = None,
) -> StandardsReport:
    """Check a drawing against drafting conventions.

    Layer comparison is case-insensitive because AutoCAD treats layer names that
    way, and a shop that types "FRAME" one day and "Frame" the next should not
    get two findings for one layer.
    """
    doc = load(path)
    present = {layer.dxf.name.upper() for layer in doc.layers}
    findings: list[StandardsFinding] = []

    for name in required_layers or []:
        if name.upper() not in present:
            findings.append(StandardsFinding("required_layer", "error", f"Layer {name!r} is missing."))

    for name in forbidden_layers or []:
        if name.upper() in present:
            findings.append(StandardsFinding("forbidden_layer", "error", f"Layer {name!r} should not be present."))

    if require_units:
        actual = _UNITS.get(doc.header.get("$INSUNITS", 0), "unknown")
        if actual != require_units:
            findings.append(
                StandardsFinding("units", "error", f"Drawing units are {actual}, expected {require_units}.")
            )

    # An empty layer is not an error, but it is the usual sign of a template that
    # was copied and half-used, so it is reported at a lower severity.
    counts = Counter(e.dxf.layer for e in doc.modelspace() if e.dxf.hasattr("layer"))
    for layer in doc.layers:
        name = layer.dxf.name
        if name != "0" and counts.get(name, 0) == 0:
            findings.append(StandardsFinding("empty_layer", "warning", f"Layer {name!r} contains no entities."))

    return StandardsReport(
        path=str(path),
        passed=not any(f.severity == "error" for f in findings),
        findings=findings,
    )


def find_text(path: Path, needle: str) -> list[dict[str, str]]:
    """Case-insensitive substring search across TEXT, MTEXT and block attributes."""
    doc = load(path)
    hits: list[dict[str, str]] = []
    probe = needle.lower()

    for entity in doc.modelspace().query("TEXT MTEXT"):
        content = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
        if probe in content.lower():
            hits.append({"kind": entity.dxftype(), "layer": entity.dxf.layer, "text": content})

    for insert in doc.modelspace().query("INSERT"):
        for attrib in insert.attribs:
            if probe in attrib.dxf.text.lower():
                hits.append({
                    "kind": f"ATTRIB on {insert.dxf.name}",
                    "layer": insert.dxf.layer,
                    "text": f"{attrib.dxf.tag}={attrib.dxf.text}",
                })

    return hits
