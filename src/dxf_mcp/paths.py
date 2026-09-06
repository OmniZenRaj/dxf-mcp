"""Path resolution, confined to a configured root.

An MCP server hands file access to a model, so the model decides what to open.
Everything here exists to make sure that decision cannot escape a directory the
operator chose. DXF_MCP_ROOT is the whole security boundary.
"""

from __future__ import annotations

import os
from pathlib import Path

ROOT_ENV = "DXF_MCP_ROOT"


class PathNotAllowed(Exception):
    """Raised when a requested path resolves outside the configured root."""


def configured_root() -> Path:
    """The directory this server is allowed to read, resolved and symlink-free.

    Defaults to the process working directory, which keeps `dxf-mcp` runnable
    without configuration while still confining it to somewhere deliberate.
    """
    return Path(os.environ.get(ROOT_ENV, os.getcwd())).expanduser().resolve()


def resolve(candidate: str | os.PathLike[str]) -> Path:
    """Resolve `candidate` inside the root, or refuse.

    Resolution happens before the containment test, so `..` segments and
    symlinks pointing outside the root are both caught. A relative path is taken
    as relative to the root rather than to the process working directory, which
    is what a caller naturally means.
    """
    root = configured_root()
    raw = Path(candidate).expanduser()
    target = (raw if raw.is_absolute() else root / raw).resolve()

    if target != root and root not in target.parents:
        raise PathNotAllowed(
            f"{target} is outside the configured root {root}. "
            f"Set {ROOT_ENV} to the directory holding the drawings."
        )
    return target


def find_dxf_files(directory: str | os.PathLike[str] = ".", recursive: bool = True) -> list[Path]:
    """Every .dxf file under `directory`, sorted, confined to the root."""
    base = resolve(directory)
    if not base.is_dir():
        return []
    pattern = "**/*.dxf" if recursive else "*.dxf"
    return sorted(p for p in base.glob(pattern) if p.is_file())
