#!/usr/bin/env python3
"""guard.py -- second gate: detect Cadence library data in an outbox record.

Pure standard library. No yaml, no network, no third-party imports, because this
file must keep working on an air-gapped machine whose Python may be minimal.

Two kinds of action:
  reject    -- the record must not be committed; caller prints file:line:rule
  substitute -- a master/cell name is replaced by a stable placeholder

Design rule: when in doubt, redact. A false positive costs the model one edit
round; a false negative leaks PDK data outside the airgap.

Imported by outbox.py. Also runnable standalone:
    python guard.py <file.md> [--own-cells PATH] [--cell-map PATH]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# --------------------------------------------------------------------------
# vocabularies
# --------------------------------------------------------------------------

# Tokens that are never PDK cell names: SPICE/Spectre parameters, keywords,
# units, node-ish words, EDA tool and harness names. Kept lowercase; matching
# is case-insensitive.
STOPWORDS = {
    # spectre / spice keywords and analysis names
    "include", "ahdl_include", "section", "endsection", "ends", "end", "subckt",
    "parameters", "parameter", "library", "corner", "corners", "sweep",
    "temp", "temperature", "tnom", "option", "options", "simulator", "lang",
    "save", "saveall", "probe", "output", "info", "elements", "rawfile",
    "dc", "ac", "tran", "transient", "op", "operatingpoint", "noise", "xf",
    "pss", "pac", "pnoise", "psp", "pno", "qpss", "sp", "spp", "envlp",
    "montecarlo", "mc", "nom", "stat", "process", "mismatch", "variations",
    "source", "sources", "vsdc", "vsac", "vsrc", "isrc", "vdc", "idc",
    "pwl", "pwlin", "sin", "sine", "pulse", "exp", "sffm", "noise_source",
    # instance prefixes (the letter block, not the master)
    "m1", "m2", "m3", "m4", "x1", "x2", "r1", "r2", "c1", "c2", "v1", "v2",
    # parameter names
    "w", "l", "m", "nf", "multi", "mult", "area", "perim", "pj", "as", "ad",
    "ps", "pd", "rs", "rd", "n", "wn", "wp", "ln", "lp", "cw", "cl", "cr",
    "r", "c", "v", "i", "q", "f", "gm", "gds", "ids", "vds", "vgs", "vth",
    "vth0", "vdsat", "vov", "vdss", "ic", "scale", "geo", "delta", "ad_ms",
    "level", "beta", "kp", "vto", "lambda", "gamma", "phi", "u0", "vmax",
    "tox", "nsub", "nss", "xj", "ld", "cgso", "cgdo", "cgbo", "lambda1",
    "nf1", "nf2", "sw", "sh", "w1", "w2", "l1", "l2", "sp1", "sp2",
    # common node / net names
    "gnd", "vss", "vdd", "vcc", "vin", "vout", "vinp", "vinn", "vop", "von",
    "outp", "outn", "inp", "inn", "bias", "vbias", "ibias", "clk", "ck",
    "n1", "n2", "n3", "n4", "n5", "n6", "n7", "n8", "n9", "n0",
    # corners
    "tt", "ff", "ss", "sf", "fs", "tt_25c", "ff_125c", "ss_m40c",
    # EDA tools, harnesses, formats -- naming these is not library data
    "virtuoso", "spectre", "spectrexl", "ade", "adexl", "maestro", "cadence",
    "calibre", "diva", "assura", "skill", "ocean", "oceanv", "oceanx",
    "dsb", "dsh", "arcadia", "analog", "netlist", "cdl", "spice", "hspice",
    "ngspice", "matlab", "simulink", "python", "linux", "windows",
    # unit suffixes / magnitudes used in values
    "u", "p", "k", "meg", "g", "t", "mv", "uv", "na", "ua", "ma",
    "pf", "uf", "ns", "us", "ms", "kohm", "megohm", "hz",
    "khz", "mhz", "ghz", "db", "dbm", "deg", "rad", "si", "sr",
}

# Prefixes that, combined with a digit, almost always mean a PDK device master
# rather than the project's own cell. Configurable via references/guard-rules.md.
DEVICE_PREFIXES = (
    "nmos", "pmos", "nch", "pch", "nfet", "pfet", "npn", "pnp", "bjt",
    "rpoly", "rpo", "polyres", "poly", "mim", "mom", "moscap", "var",
    "res", "cap", "ind", "dio", "diode", "scr", "esd", "ldmos", "hvt",
    "lvt", "rvt", "svt", "uhvt", "ulvt", "sgt", "dgt", "hpt", "hsl",
)

# Placeholder forms that are explicitly allowed to look like paths.
ALLOWED_PATH_PLACEHOLDERS = ("/path/to/", "<path>", "<project>", "<user>", "{{")

FENCE_RE = re.compile(r"^\s*(```|~~~)")
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{2,39}")

# Spectre instance:  inst (nodes) master params...
SPECTRE_MASTER_RE = re.compile(
    r"^\s*[A-Za-z_][A-Za-z0-9_]*\s*\([^()]*\)\s*([A-Za-z_][A-Za-z0-9_]*)"
)
# SPICE instance:  M1 d g s b nmos1v w=...   /  X1 a b c subckt_name
SPICE_MASTER_RE = re.compile(
    r"^\s*[MNXCRVDLJKE][A-Za-z0-9_]+\s+(?:\S+\s+){3,5}?([a-z][a-z0-9_]*)\s+"
)


class Finding:
    """One guard hit. line is 1-based; snippet is trimmed to 90 chars."""

    __slots__ = ("action", "line", "note", "rule", "snippet")

    def __init__(self, rule: str, line: int, snippet: str, action: str, note: str = ""):
        self.rule = rule
        self.line = line
        self.snippet = snippet.strip()[:90]
        self.action = action  # "reject" | "warn"
        self.note = note

    def render(self, path: str = "") -> str:
        where = f"{path}:{self.line}" if path else f"line {self.line}"
        tail = f"  ({self.note})" if self.note else ""
        return f"  [reject] {where} {self.rule}: {self.snippet!r}{tail}"

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Finding({self.rule}, line={self.line}, action={self.action})"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _has_digit(tok: str) -> bool:
    return any(ch.isdigit() for ch in tok)


def is_code_fence(line: str) -> bool:
    return bool(FENCE_RE.match(line))


def _looks_like_cell(tok: str) -> bool:
    """True if tok plausibly names a PDK device master."""
    low = tok.lower()
    if low in STOPWORDS:
        return False
    if not _has_digit(low):
        return False
    if not low.startswith(DEVICE_PREFIXES):
        return False
    return True


# --------------------------------------------------------------------------
# reject rules R0-R5, R7
# --------------------------------------------------------------------------

R1_MODEL_CARD = re.compile(
    r"^\s*(?:\.?\s*model|\.?\s*subckt)\s+[A-Za-z_][\w]*\s+"
    r"(?:nmos|pmos|npn|pnp|r|rres|c|ramp|dio|ind|nmos_hvt|pmos_lvt)\b",
    re.IGNORECASE,
)
R1_BLOCK = re.compile(
    r"^\s*(?:\.lib|library|section|endsection|corner\s+[\w]+\s*\{|simulator\s+lang\s*=)",
    re.IGNORECASE,
)
R2_INCLUDE = re.compile(
    r"^\s*(?:\.include|include|ahdl_include|spectre\s+include)\b\s*[\"']?([^\s\"']+)",
    re.IGNORECASE,
)
# R3 rejects DATA, not vocabulary. Naming a tool or a check ("the Calibre DRC
# run failed") is a legitimate problem report and leaks nothing; a deck file
# name or a named tech file does leak. Bare vocabulary is a W2 warn instead --
# an earlier revision rejected on vocabulary alone and that blocked the record
# template's own instruction text, plus any honest DRC/LVS bug report.
R3_DECK_FILE = re.compile(
    r"[\w\-\./\\]+\.(?:oa|lib|cdl|tf|svrf|drcs|cdb|gds|gdsii)\b", re.IGNORECASE
)
R3_NAMED_DECK = re.compile(
    r"(?:tech\s?file|rule\s*deck|layermap|liberty|openaccess|stream\s*out)"
    r"\s*[:=]?\s*[\w\-\./\\]+\.\w+",
    re.IGNORECASE,
)
W2_VOCAB = re.compile(
    r"\b(techfile|tech\s+file|liberty|rule\s*deck|layermap|assura|diva|calibre"
    r"|antenna|drc|lvs|openaccess|gdsii|stream\s*out|cdl)\b",
    re.IGNORECASE,
)
R4_HEADER_TELL = re.compile(
    r"(library\s+name\s*:\s*(?!\s*<)(?!\s*unknown)|cell\s+name\s*:\s*(?!\s*<)(?!\s*unknown)"
    r"|libId\s*[:=]|cellView\s*[:=]|view\s+name\s*:\s*(?!\s*<))",
    re.IGNORECASE,
)
R5_PATHS = re.compile(
    r"(?:[A-Za-z]:[\\/](?!\s)|//[A-Za-z0-9_.\-]+/[A-Za-z]|\\\\[A-Za-z0-9_.\-]+\\\\"
    r"|/home/[A-Za-z0-9_.\-]|/opt/[A-Za-z0-9_.\-]|/eda/[A-Za-z0-9_.\-]"
    r"|/Users/[A-Za-z0-9_.\-]|/mnt/[A-Za-z0-9_.\-]|/project/[A-Za-z0-9_.\-])"
)


def _line_hits(line: str, lineno: int) -> list[Finding]:
    out: list[Finding] = []
    stripped = line.strip()
    if not stripped:
        return out

    if R1_MODEL_CARD.search(line):
        out.append(Finding("R1", lineno, line, "reject", "SPICE/Spectre model card or subckt body"))
    if R1_BLOCK.search(line):
        out.append(Finding("R1", lineno, line, "reject", "library / section / .lib block"))
    if R3_DECK_FILE.search(line):
        out.append(Finding("R3", lineno, line, "reject", "library / deck / layout file name"))
    if R3_NAMED_DECK.search(line):
        out.append(Finding("R3", lineno, line, "reject", "named tech file or rule deck"))
    if R4_HEADER_TELL.search(line):
        out.append(Finding("R4", lineno, line, "reject", "Cadence library/cell/view header tell"))

    m = R2_INCLUDE.search(line)
    if m:
        target = m.group(1)
        if not any(p in target for p in ALLOWED_PATH_PLACEHOLDERS):
            out.append(Finding("R2", lineno, line, "reject", f"real include path {target!r}"))

    low = line.lower()
    if not any(p in low for p in ALLOWED_PATH_PLACEHOLDERS):
        if R5_PATHS.search(line):
            out.append(Finding("R5", lineno, line, "reject", "absolute / vendor / UNC path"))
    return out


def scan_rejects(text: str, in_code_only: bool = False) -> list[Finding]:
    """R1-R5 across every line. in_code_only is unused today but keeps the
    signature stable for future rules that must distinguish prose from netlist."""
    out: list[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        out.extend(_line_hits(line, i))
    return out


def scan_placeholders(text: str) -> list[Finding]:
    """R0: template placeholder left unfilled."""
    out: list[Finding] = []
    for i, line in enumerate(text.splitlines(), start=1):
        for m in re.finditer(r"\{\{[^}\n]{0,60}\}\}", line):
            out.append(Finding("R0", i, line, "reject", f"unfilled placeholder {m.group(0)}"))
    return out


def scan_prose_cellnames(text: str, own_cells: set[str]) -> list[Finding]:
    """R7: a PDK-looking master name written in prose (outside code fences).

    Rejects instead of substituting, because prose should carry a generic class
    word ("a low-voltage NMOS") rather than a placeholder token.
    """
    out: list[Finding] = []
    in_code = False
    for i, line in enumerate(text.splitlines(), start=1):
        if is_code_fence(line):
            in_code = not in_code
            continue
        if in_code:
            continue
        for tok in TOKEN_RE.findall(line):
            if tok in own_cells or tok.lower() in {c.lower() for c in own_cells}:
                continue
            if _looks_like_cell(tok):
                out.append(Finding(
                    "R7", i, line, "reject",
                    f"{tok!r} looks like a PDK master name; write a generic "
                    f"class word instead, or add it to _local/own-cells.txt if "
                    f"it is this project's own cell",
                ))
    return out


# --------------------------------------------------------------------------
# R6: substitute master names inside code fences
# --------------------------------------------------------------------------

def split_code_spans(lines: list[str]) -> list[bool]:
    """Return a parallel list telling whether each line sits inside a fence."""
    flags: list[bool] = []
    in_code = False
    for line in lines:
        if is_code_fence(line):
            flags.append(True)  # the fence line itself is not content
            in_code = not in_code
            continue
        flags.append(in_code)
    return flags


def _next_placeholder(cell_map: dict[str, str]) -> str:
    used = set()
    for ph in cell_map.values():
        m = re.fullmatch(r"<cell_(\d{3})>", ph)
        if m:
            used.add(int(m.group(1)))
    n = 1
    while n in used:
        n += 1
    return f"<cell_{n:03d}>"


def substitute_masters(
    text: str, own_cells: set[str], cell_map: dict[str, str]
) -> tuple[str, list[tuple[str, str]]]:
    """Replace master/cell names inside code fences with stable placeholders.

    cell_map is mutated in place (real name -> placeholder) so the caller can
    persist it. Returns (new_text, [(real, placeholder), ...]).
    """
    lines = text.splitlines(keepends=True)
    flags = split_code_spans([l.rstrip("\n") for l in lines])
    subs: list[tuple[str, str]] = []
    own_lower = {c.lower() for c in own_cells}

    def placeholder_for(real: str) -> str:
        key = real.lower()
        if key in cell_map:
            return cell_map[key]
        ph = _next_placeholder(cell_map)
        cell_map[key] = ph
        return ph

    for idx, line in enumerate(lines):
        if not flags[idx]:
            continue
        if line.lstrip().startswith(("```", "~~~")):
            continue
        body = line.rstrip("\n")
        trailing = line[len(body):]

        masters: set[str] = set()
        m = SPECTRE_MASTER_RE.match(body)
        if m:
            masters.add(m.group(1))
        m2 = SPICE_MASTER_RE.match(body)
        if m2:
            masters.add(m2.group(1))
        # broad sweep: any device-prefixed token with a digit inside a netlist
        for tok in TOKEN_RE.findall(body):
            if _looks_like_cell(tok):
                masters.add(tok)

        if not masters:
            continue
        for real in sorted(masters, key=len, reverse=True):
            if real.lower() in own_lower:
                continue
            ph = placeholder_for(real)
            pattern = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(real)}(?![A-Za-z0-9_])")
            new_body, n = pattern.subn(ph, body)
            if n:
                body = new_body
                subs.append((real, ph))
        lines[idx] = body + trailing

    return "".join(lines), subs


# --------------------------------------------------------------------------
# warn rules W1
# --------------------------------------------------------------------------

def scan_warns(text: str, max_lines: int = 200, max_evidence: int = 30) -> list[Finding]:
    out: list[Finding] = []
    lines = text.splitlines()
    if len(lines) > max_lines:
        out.append(Finding("W1", len(lines), f"{len(lines)} lines", "warn",
                           f"record longer than {max_lines} lines"))
    flags = split_code_spans(lines)
    run = 0
    for i, inside in enumerate(flags, start=1):
        if inside:
            run += 1
            if run == max_evidence + 1:
                out.append(Finding("W1", i, lines[i - 1], "warn",
                                   f"code evidence longer than {max_evidence} lines"))
        else:
            run = 0
    # W2: EDA vocabulary is allowed, but a human should eyeball those lines
    # before the record leaves the airgap.
    for i, line in enumerate(lines, start=1):
        m = W2_VOCAB.search(line)
        if m:
            out.append(Finding("W2", i, line, "warn",
                               f"EDA vocabulary {m.group(0)!r}: allowed, verify no "
                               "deck content rides along on this line"))
    return out


# --------------------------------------------------------------------------
# entry point used by outbox.py
# --------------------------------------------------------------------------

def scan(text: str, own_cells: set[str], cell_map: dict[str, str]) -> dict:
    """Full two-pass scan. Returns a dict:
        rejects : list[Finding]
        warns   : list[Finding]
        text    : substituted text (only meaningful when rejects is empty)
        subs    : list[(real, placeholder)]
    """
    rejects: list[Finding] = []
    rejects.extend(scan_placeholders(text))
    rejects.extend(scan_rejects(text))
    rejects.extend(scan_prose_cellnames(text, own_cells))
    warns = scan_warns(text)
    new_text, subs = substitute_masters(text, own_cells, cell_map)
    return {"rejects": rejects, "warns": warns, "text": new_text, "subs": subs}


# --------------------------------------------------------------------------
# standalone CLI
# --------------------------------------------------------------------------

def load_own_cells(path: Path | None) -> set[str]:
    if path is None or not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tok = line.split("#", 1)[0].strip()
        if tok:
            out.add(tok)
    return out


def load_cell_map(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip().strip("'\"")] = v.strip().strip("'\"")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Scan a record for Cadence library data.")
    ap.add_argument("file", help="Markdown record to scan")
    ap.add_argument("--own-cells", default=None, help="whitelist file, one cell per line")
    ap.add_argument("--cell-map", default=None, help="real -> placeholder map file")
    ap.add_argument("--show-substituted", action="store_true",
                    help="print the redacted text to stdout")
    args = ap.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"[reject] no such file: {path}")
        return 2
    text = path.read_text(encoding="utf-8", errors="replace")
    own = load_own_cells(Path(args.own_cells) if args.own_cells else None)
    cmap = load_cell_map(Path(args.cell_map) if args.cell_map else None)

    res = scan(text, own, cmap)
    if res["rejects"]:
        print(f"[reject] {len(res['rejects'])} rule hit(s) in {path}")
        for f in res["rejects"]:
            print(f.render(str(path)))
        return 1
    print(f"[ok] {path} passes guard")
    if res["subs"]:
        print(f"[ok] substituted {len(res['subs'])} master name(s): "
              + ", ".join(f"{r}->{p}" for r, p in res["subs"]))
    for w in res["warns"]:
        print(f"  [warn] {w.rule} line {w.line}: {w.note}")
    if args.show_substituted:
        print("---- redacted text ----")
        print(res["text"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
