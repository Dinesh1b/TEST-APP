"""
module_registry.py — Single Source of Truth for module definitions.

Loads modules.json and exposes lookup helpers used by both the
Flask backend (execution engine, config builder) and the CLI runner.
"""

import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
_MODULES_JSON = os.path.join(_PROJECT_ROOT, "modules.json")

_registry = None  # lazy-loaded cache


def _load():
    global _registry
    if _registry is not None:
        return _registry
    with open(_MODULES_JSON, "r", encoding="utf-8") as f:
        _registry = json.load(f)
    return _registry


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_all_modules() -> list[dict]:
    """Return the full list of module definitions."""
    return _load()["modules"]


def get_groups() -> list[dict]:
    """Return the group definitions."""
    return _load()["groups"]


def get_module_by_idx(idx: int) -> dict | None:
    """Lookup a module by its index."""
    for m in get_all_modules():
        if m["idx"] == idx:
            return m
    return None


def get_module_by_flag(flag: str) -> dict | None:
    """Lookup a module by its run-flag key (e.g. 'run_q_setting')."""
    for m in get_all_modules():
        if m["flag"] == flag:
            return m
        if m.get("alt_flag") == flag:
            return m
    return None


def flag_to_idx(flag: str) -> int | None:
    """Convert a run-flag string to its module index."""
    m = get_module_by_flag(flag)
    return m["idx"] if m else None


def idx_to_flag(idx: int) -> str | None:
    """Convert a module index to its primary run-flag string."""
    m = get_module_by_idx(idx)
    return m["flag"] if m else None


def get_module_keys() -> list[tuple[str, str]]:
    """
    Return MODULE_KEYS compatible list: [(flag, name), ...]
    Drop-in replacement for the hardcoded MODULE_KEYS in old app.py.
    """
    result = []
    for m in get_all_modules():
        result.append((m["flag"], m["name"]))
        if m.get("alt_flag"):
            result.append((m["alt_flag"], m["name"]))
    return result


def get_idx_to_flag_map() -> dict[int, str]:
    """Return {idx: flag} mapping for all modules."""
    return {m["idx"]: m["flag"] for m in get_all_modules()}


def get_flag_to_idx_map() -> dict[str, int]:
    """Return {flag: idx} mapping, including alt_flags."""
    result = {}
    for m in get_all_modules():
        result[m["flag"]] = m["idx"]
        if m.get("alt_flag"):
            result[m["alt_flag"]] = m["idx"]
    return result


def reload():
    """Force-reload modules.json (useful after edits)."""
    global _registry
    _registry = None
    return _load()
