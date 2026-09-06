#!/usr/bin/env python
"""End-to-end check: drive the installed server over real stdio JSON-RPC.

The unit tests exercise the DXF and path logic directly. This proves the MCP
wiring on top of them actually answers a client, which is the part unit tests
cannot see. Run it after changing anything in server.py.

    .venv/bin/python scripts/smoke_test.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile

import ezdxf


def build_fixture(root: pathlib.Path) -> None:
    doc = ezdxf.new("R2010", setup=False)
    doc.header["$INSUNITS"] = 4
    doc.layers.add("FRAME", color=1)
    block = doc.blocks.new("PART")
    for offset, tag in enumerate(("PARTNO", "QTY")):
        block.add_attdef(tag=tag, insert=(0, -offset))
    msp = doc.modelspace()
    msp.add_blockref("PART", (0, 0), dxfattribs={"layer": "FRAME"}).add_auto_attribs(
        {"PARTNO": "CCI-1042", "QTY": "4"}
    )
    doc.saveas(str(root / "assembly.dxf"))


def main() -> int:
    root = pathlib.Path(tempfile.mkdtemp(prefix="dxf-smoke-"))
    build_fixture(root)

    server = pathlib.Path(__file__).resolve().parent.parent / ".venv" / "bin" / "dxf-mcp"
    proc = subprocess.Popen(
        [str(server)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, bufsize=1, env=dict(os.environ, DXF_MCP_ROOT=str(root)),
    )

    def send(payload: dict) -> None:
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def read() -> dict:
        while True:
            line = proc.stdout.readline()
            if not line:
                raise SystemExit("server closed stdout\n" + proc.stderr.read())
            if line.strip().startswith("{"):
                return json.loads(line)

    failures: list[str] = []

    send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {},
        "clientInfo": {"name": "smoke", "version": "0"}}})
    info = read()["result"]["serverInfo"]
    print(f"initialize        {info['name']} {info.get('version') or '(no version)'}")
    if not info.get("version"):
        failures.append("serverInfo carries no version")

    send({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})

    send({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    names = [t["name"] for t in read()["result"]["tools"]]
    print(f"tools/list        {len(names)}: {', '.join(names)}")
    expected = {"list_drawings", "drawing_summary", "list_layers",
                "extract_bill_of_materials", "check_standards", "find_text"}
    if missing := expected - set(names):
        failures.append(f"missing tools: {sorted(missing)}")

    send({"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
        "name": "extract_bill_of_materials", "arguments": {"path": "assembly.dxf"}}})
    result = read()["result"]
    bom = result.get("structuredContent") or json.loads(result["content"][0]["text"])
    print(f"bill of materials {bom['row_count']} row(s), columns {bom['attribute_columns']}")
    if bom["row_count"] != 1 or bom["rows"][0]["attributes"]["PARTNO"] != "CCI-1042":
        failures.append("bill of materials did not come back as expected")

    send({"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
        "name": "drawing_summary", "arguments": {"path": "../../../etc/passwd"}}})
    escaped = read()["result"]
    print(f"traversal         refused={bool(escaped.get('isError'))}")
    if not escaped.get("isError"):
        failures.append("path traversal was NOT refused")

    proc.stdin.close()
    proc.terminate()

    if failures:
        print("\nFAILED:")
        for line in failures:
            print(f"  - {line}")
        return 1
    print("\nall checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
