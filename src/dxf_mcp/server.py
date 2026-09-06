"""MCP server exposing DXF drawings as tools.

Six tools, all read-only. The interesting one is `extract_bill_of_materials`:
turning block attributes into rows is the step between a drawing and an ERP, and
it is the step people still do by hand.
"""

from __future__ import annotations

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

from . import __version__, drawings, paths

mcp = MCPServer(
    name="dxf",
    title="DXF Drawings",
    version=__version__,
    instructions=(
        "Read-only access to DXF drawings under a configured root directory. "
        "Call drawing_summary first: it is cheap and tells you which other tool is worth calling. "
        "extract_bill_of_materials reads block attributes, so a drawing that records parts as loose "
        "text rather than attributed blocks returns no rows; use find_text for those."
    ),
)


def _resolve(path: str):
    """Resolve a caller-supplied path, converting refusals into tool errors."""
    try:
        target = paths.resolve(path)
    except paths.PathNotAllowed as exc:
        raise ToolError(str(exc)) from exc
    if not target.is_file():
        raise ToolError(f"No such file: {path}")
    return target


@mcp.tool()
def list_drawings(directory: str = ".", recursive: bool = True) -> list[str]:
    """List DXF files available under a directory, relative to the configured root."""
    try:
        found = paths.find_dxf_files(directory, recursive)
    except paths.PathNotAllowed as exc:
        raise ToolError(str(exc)) from exc
    root = paths.configured_root()
    return [str(p.relative_to(root)) for p in found]


@mcp.tool()
def drawing_summary(path: str) -> drawings.DrawingSummary:
    """Describe one drawing: DXF version, units, layer and block counts, entity mix.

    Call this first. It is cheap, and it tells you which of the other tools is
    worth calling on this file.
    """
    try:
        return drawings.summarize(_resolve(path))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def list_layers(path: str) -> list[drawings.LayerInfo]:
    """List every layer in a drawing with its colour, linetype, state and entity count."""
    try:
        return drawings.layers(_resolve(path))
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def extract_bill_of_materials(path: str, block: str | None = None) -> drawings.BillOfMaterials:
    """Extract a bill of materials from block insertions and their attributes.

    Each placed block becomes a row and each attribute tag becomes a column, which
    is the shape drawing data has to be in before it can reach an ERP or a PLM
    record. Pass `block` to restrict the extract to one block name.
    """
    try:
        return drawings.bill_of_materials(_resolve(path), block)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def check_standards(
    path: str,
    required_layers: list[str] | None = None,
    forbidden_layers: list[str] | None = None,
    require_units: str | None = None,
) -> drawings.StandardsReport:
    """Check a drawing against drafting standards.

    Reports missing required layers, forbidden layers and wrong units as errors,
    and empty layers as warnings. `passed` reflects errors only, so a drawing with
    warnings still passes.
    """
    try:
        return drawings.check_standards(_resolve(path), required_layers, forbidden_layers, require_units)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.tool()
def find_text(path: str, needle: str) -> list[dict[str, str]]:
    """Search TEXT, MTEXT and block attributes for a substring, case-insensitively.

    Useful for locating a part number or a revision note when you do not yet know
    which block or layer it lives on.
    """
    if not needle.strip():
        raise ToolError("needle must not be empty.")
    try:
        return drawings.find_text(_resolve(path), needle)
    except ValueError as exc:
        raise ToolError(str(exc)) from exc


@mcp.resource("dxf://root")
def root() -> str:
    """The directory this server is confined to."""
    return str(paths.configured_root())


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
