"""Charger les protocoles Blizzard installés, sans leur ancien chargeur `imp`."""
from __future__ import annotations

import importlib.util
import re
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=8)
def load_protocol(build: int | None = None, *, directory: Path | None = None):
    if directory is None:
        import heroprotocol

        directory = Path(heroprotocol.__file__).parent / "versions"
    paths = {int(match[1]): path for path in directory.iterdir()
             if (match := re.fullmatch(r"protocol([0-9]+)\.py", path.name))}
    if build is None:
        if not paths:
            raise ModuleNotFoundError("aucun protocole Blizzard installé")
        build = max(paths)
    if build not in paths:
        raise ModuleNotFoundError(f"protocole Blizzard {build} absent")
    spec = importlib.util.spec_from_file_location(f"protocol{build:05d}", paths[build])
    if spec is None or spec.loader is None:
        raise ImportError("chargeur de protocole indisponible")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
