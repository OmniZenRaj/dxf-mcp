# dxf-mcp

An MCP server that gives an agent structured, read-only access to DXF drawings.

Most CAD automation exists to answer three questions, and shops still answer them
by hand: what is in this drawing, what parts does it place, and does it follow our
standards. This exposes those as tools, so a model can ask instead of a person
opening the file.

Nothing here writes a drawing. The server reads.

## Tools

| Tool | What it does |
|---|---|
| `list_drawings` | DXF files under a directory, relative to the configured root |
| `drawing_summary` | DXF version, units, layer and block counts, entity mix |
| `list_layers` | Every layer with colour, linetype, on/locked state, entity count |
| `extract_bill_of_materials` | Block insertions and their attributes, flattened into rows |
| `check_standards` | Required layers, forbidden layers, expected units, empty layers |
| `find_text` | Case-insensitive search across TEXT, MTEXT and block attributes |

`extract_bill_of_materials` is the one worth explaining. A block insertion with
attributes is how a drawing records a placed component: `PARTNO`, `QTY`,
`MATERIAL`. Turning those into one row per component with attribute tags as
columns is the step between a drawing and an ERP or PLM record, and it is
normally either a bespoke LISP routine per shop or a person retyping.

## Install

```bash
git clone https://github.com/OmniZenRaj/dxf-mcp
cd dxf-mcp
python3 -m venv .venv && .venv/bin/pip install -e .
```

## Configure

Point `DXF_MCP_ROOT` at the directory holding your drawings. Claude Desktop, in
`claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "dxf": {
      "command": "/absolute/path/to/dxf-mcp/.venv/bin/dxf-mcp",
      "env": { "DXF_MCP_ROOT": "/absolute/path/to/your/drawings" }
    }
  }
}
```

VS Code, in `.vscode/mcp.json`:

```json
{
  "servers": {
    "dxf": {
      "type": "stdio",
      "command": "/absolute/path/to/dxf-mcp/.venv/bin/dxf-mcp",
      "env": { "DXF_MCP_ROOT": "/absolute/path/to/your/drawings" }
    }
  }
}
```

## The root is the security boundary

An MCP server hands file access to a model, which means the model chooses what to
open. `DXF_MCP_ROOT` is the only thing standing between that and the rest of the
disk, so it is enforced in one place and tested directly.

Paths are resolved before the containment check, so `../../etc/passwd` and a
symlink pointing outside the root are both refused rather than followed. Relative
paths are taken as relative to the root, not to the process working directory,
because that is what a caller means. If `DXF_MCP_ROOT` is unset the root is the
working directory, which keeps the server runnable without configuration while
still confining it somewhere deliberate.

## Example

```
> Which drawings under ./assemblies are missing a DIMENSIONS layer?

  list_drawings("assemblies")
  check_standards(path, required_layers=["DIMENSIONS"])   # per drawing

> Give me a parts list for assembly.dxf

  extract_bill_of_materials("assembly.dxf")
  -> 2 rows, columns MATERIAL / PARTNO / QTY
     PART  CCI-1042  qty 4  Oak    (layer FRAME)
     PART  CCI-2088  qty 1  Steel  (layer PANEL)
```

## Tests

```bash
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest                        # 16 unit tests
.venv/bin/python scripts/smoke_test.py  # real stdio JSON-RPC against the built server
```

Fixtures build a real DXF document with `ezdxf` rather than checking in a binary,
so the test drawing is readable as code and easy to extend.

The unit tests cover the DXF and path logic directly. The smoke test drives the
installed executable over stdio -- initialize, `tools/list`, a real
`extract_bill_of_materials` call, and a path-traversal attempt that must come back
`isError` -- because the MCP wiring is the part unit tests cannot see.

The confinement tests were checked by breaking the code on purpose: deleting the
containment condition fails three of them, and resolving the path after the check
rather than before fails the traversal and symlink cases. A test that never fails
is not evidence.

## Limitations

Reads DXF, not DWG. DWG is a closed format; converting with ODA File Converter or
`dwg2dxf` first is the usual route.

Bills of material come from block attributes. A drawing that records parts as
loose text rather than attributed blocks will produce no rows, which is correct
behaviour and not a bug, though `find_text` will still locate the text.

## Licence

MIT.
