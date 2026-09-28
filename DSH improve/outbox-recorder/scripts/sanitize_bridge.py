#!/usr/bin/env python3
"""sanitize_bridge.py -- first gate: reuse arcadia-1's own sanitizer.

arcadia-1 (analog-agents) already ships a token-replacement sanitizer:
    tools/sanitize_snapshot.py   -> load_token_map(), sanitize_text()
    tools/sanitizer.py           -> get_sanitize_fn()
    _local/sanitize-map.yml      -> flat {src: dst} table

This bridge imports those functions when it can find them, layers our own
_local/outbox-map.yml on top, and DEGRADES GRACEFULLY when it cannot:

  * arcadia-1 not found      -> [warn], built-in rules only, exit 0
  * PyYAML missing           -> fall back to a key=value line parser
  * map file missing         -> empty map, no error

Rationale: this runs on an air-gapped box with a weak model driving it. A crash
here would silently disable redaction, which is worse than running with fewer
rules. Every degradation prints one ASCII [warn] line so the human sees it.

Imported by outbox.py. Standalone:
    python sanitize_bridge.py --selftest
    python sanitize_bridge.py --text "some text"
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

SKILL_ROOT = Path(__file__).resolve().parents[1]
LOCAL = SKILL_ROOT / "_local"
OUR_MAP = LOCAL / "outbox-map.yml"
CONFIG = LOCAL / "config.yml"

# Where to look for analog-agents when nothing is configured. Siblings of the
# DSH discovery root first, then the arcadia-1 layout seen on this project.
CANDIDATE_ROOTS = (
    "ANALOG_AGENTS_ROOT",
    "ARCADIA1_ROOT",
)
CANDIDATE_RELPATHS = (
    "../analog-agents",
    "../../analog-agents",
    "../../arcadia-1/analog-agents",
    "../arcadia-1/analog-agents",
)
SANITIZE_MODULE_RELPATH = Path("tools") / "sanitize_snapshot.py"

# Built-in fallback table: vendor/toolchain tells that must never leave the
# airgap even when arcadia-1's own map is unavailable. Deliberately small and
# obvious; guard.py handles the structural rules.
BUILTIN_MAP = {
    "/home/": "<userhome>/",
    "/opt/": "<vendorpath>/",
    "/eda/": "<edapath>/",
}


class Bridge:
    """Holds whatever sanitizing capability we managed to assemble."""

    def __init__(self) -> None:
        self.tokens: dict[str, str] = {}
        self.arcadia_root: Path | None = None
        self.using_arcadia = False
        self.warnings: list[str] = []

    # -- loading ----------------------------------------------------------
    def _read_config_value(self, key: str) -> str | None:
        if not CONFIG.exists():
            return None
        for line in CONFIG.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            k, v = line.split(":", 1)
            if k.strip() == key:
                return v.strip().strip("'\"")
        return None

    def find_arcadia(self) -> Path | None:
        for env in CANDIDATE_ROOTS:
            val = os.environ.get(env) or self._read_config_value(env.lower())
            if val:
                p = Path(val)
                if (p / SANITIZE_MODULE_RELPATH).exists():
                    return p
                self.warnings.append(
                    f"{env}={val} does not contain tools/sanitize_snapshot.py"
                )
        for rel in CANDIDATE_RELPATHS:
            p = (SKILL_ROOT / rel).resolve()
            if (p / SANITIZE_MODULE_RELPATH).exists():
                return p
        return None

    @staticmethod
    def _parse_map_lines(text: str) -> dict[str, str]:
        """Dependency-free parser for a flat mapping.

        Accepts real YAML (`src: dst`) and `src=dst`. Ignores comments, blank
        lines, nested structures and list items -- our maps are flat by design.
        """
        out: dict[str, str] = {}
        for raw in text.splitlines():
            line = raw.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            stripped = line.strip()
            if stripped.startswith(("-", "sanitize:")):
                continue
            sep = ":" if ":" in stripped else ("=" if "=" in stripped else None)
            if sep is None:
                continue
            k, v = stripped.split(sep, 1)
            k = k.strip().strip("'\"")
            v = v.strip().strip("'\"")
            if k and v:
                out[k] = v
        return out

    def _load_yaml_map(self, path: Path) -> dict[str, str]:
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            import yaml  # type: ignore

            data = yaml.safe_load(text) or {}
            if isinstance(data, dict) and "sanitize" in data:
                data = data["sanitize"] or {}
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
            self.warnings.append(f"{path.name} is not a flat mapping; using line parser")
        except ImportError:
            self.warnings.append("PyYAML unavailable; parsing maps as key: value lines")
        except Exception as e:  # noqa: BLE001
            self.warnings.append(f"{path.name} failed to parse as YAML ({e}); using line parser")
        return self._parse_map_lines(text)

    def load(self) -> Bridge:
        self.tokens = dict(BUILTIN_MAP)

        root = self.find_arcadia()
        if root is None:
            self.warnings.append(
                "arcadia-1 sanitizer not found; built-in rules only"
            )
        else:
            self.arcadia_root = root
            mod = root / SANITIZE_MODULE_RELPATH
            try:
                import importlib.util

                spec = importlib.util.spec_from_file_location("a1_sanitize_snapshot", mod)
                if spec is None or spec.loader is None:
                    raise ImportError("cannot build module spec")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)  # type: ignore[union-attr]
                map_path = root / "_local" / "sanitize-map.yml"
                if map_path.exists():
                    loaded = module.load_token_map(map_path)
                    self.tokens.update({str(k): str(v) for k, v in loaded.items()})
                    self.using_arcadia = True
                else:
                    self.warnings.append(
                        f"arcadia-1 found at {root} but {map_path} is absent; "
                        "its token map is per-machine and gitignored"
                    )
            except Exception as e:  # noqa: BLE001
                self.warnings.append(f"could not import arcadia-1 sanitizer ({e})")

        # Layer the extra maps on top. arcadia-1's own map is only re-read here
        # when the import path failed -- otherwise load_token_map already did it
        # properly, with PyYAML, and a second line-parser pass would be noise.
        extras: list[Path] = [OUR_MAP]
        if root is not None and not self.using_arcadia:
            fallback = root / "_local" / "sanitize-map.yml"
            if fallback.exists():
                extras.insert(0, fallback)
        for extra in extras:
            if extra and extra.exists():
                try:
                    self.tokens.update(self._load_yaml_map(extra))
                except Exception as e:  # noqa: BLE001
                    self.warnings.append(f"could not read {extra} ({e})")
        return self

    # -- applying ---------------------------------------------------------
    def apply(self, text: str) -> tuple[str, list[tuple[str, str, int]]]:
        """Replace every mapped token. Longest keys first so a short token can
        never eat part of a longer one (same rule arcadia-1 uses)."""
        hits: list[tuple[str, str, int]] = []
        for src in sorted(self.tokens, key=len, reverse=True):
            if not src:
                continue
            n = text.count(src)
            if n:
                text = text.replace(src, self.tokens[src])
                hits.append((src, self.tokens[src], n))
        return text, hits

    def describe(self) -> str:
        origin = f"arcadia-1 @ {self.arcadia_root}" if self.using_arcadia else "built-in only"
        return f"tokens={len(self.tokens)} source={origin}"


def get_bridge() -> Bridge:
    return Bridge().load()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="First redaction gate.")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--text", default=None)
    ap.add_argument("--file", default=None)
    args = ap.parse_args(argv)

    b = get_bridge()
    print(f"[info] {b.describe()}")
    for w in b.warnings:
        print(f"[warn] {w}")

    if args.selftest:
        cases = [
            ("plain text stays", "the comparator failed to settle", "the comparator failed to settle"),
            ("builtin path redacted", "log at /home/wave/.dsh/x", "log at <userhome>/wave/.dsh/x"),
            ("longest key wins", "under /eda/tools/ and /eda/", "under <edapath>/tools/ and <edapath>/"),
        ]
        failed = 0
        for label, src, want in cases:
            got, _ = b.apply(src)
            ok = got == want
            failed += 0 if ok else 1
            print(f"  [{'ok' if ok else 'FAIL'}] {label}")
            if not ok:
                print(f"        want {want!r}")
                print(f"        got  {got!r}")
        # a mapped token from our own file, if present
        if OUR_MAP.exists():
            print(f"  [ok] own map present: {OUR_MAP}")
        print(f"[{'ok' if failed == 0 else 'FAIL'}] selftest failures={failed}")
        return 0 if failed == 0 else 1

    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    elif args.text is not None:
        text = args.text
    else:
        text = sys.stdin.read()
    out, hits = b.apply(text)
    for src, dst, n in hits:
        print(f"[hit] {n}x {src!r} -> {dst!r}")
    print("---- sanitized ----")
    print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
