#!/usr/bin/env python3
"""E-M1 Mark II halation step 3: Soft Focus route for ordinary colour stills (docs/OMD-EM1-II/HALATION.md).

    python3 patches/omdem1mk2/halation/build.py               -> edits.json (stage from sid 961)
    EM1_HL_FORCE_STAGE=1 python3 patches/omdem1mk2/halation/build.py   -> test build: stage fixed at 1..3

Edits:
  1. Section 6 loaded end 0x612e7000 -> 0x61300000 (end-getter stub word 0x60042b6d), so the loader copies the 100 KB
     gap 0x612e7000..0x61300000 from the package: the same edit as the camera-tested space probe sp1 (S+).
  2. hl_flag.s at 0x612e7000 (the gap, 0xFF in the catalog stock).
  3. Hook: the first 7 bytes of the flag converter 0x6042285e (`mov (28,a0),a3; mov a1,a2; mov 24951,a1`, all
     absolute, no branch lands inside) -> `jmp hl_entry; nop; nop`; hl_flag replays them and returns to 0x60422865.
"""
import json
import os
import struct
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TC = Path('/home/hertzel/ep7fw-toolchains/mn10300/bin')
BIN = ROOT / 'em1mk2/extracted/00_0100_40560020.decoded.bin'
B = 0x60021020
END_IMM, OLD_END, NEW_END = 0x60042B6D, 0x612E7000, 0x61300000
CODE_AT = OLD_END
HOOK, HOOK_STOCK, BACK = 0x6042285E, bytes.fromhex('f82c1c96257761'), 0x60422865
GETTER, STAGE_KEY = 0x6005E6CF, 0xF709


def force_stage():
    value = int(os.environ.get('EM1_HL_FORCE_STAGE', '0'))
    if not 0 <= value <= 3:
        raise SystemExit('EM1_HL_FORCE_STAGE must be 0..3')
    return value


def assemble(force):
    with tempfile.TemporaryDirectory() as t:
        t = Path(t)
        subprocess.run([str(TC / 'mn10300-elf-as'), f'--defsym=FORCE_STAGE={force}', str(HERE / 'hl_flag.s'),
                        '-o', str(t / 'o')], check=True)
        syms = dict(GETTER=GETTER, STAGE_KEY=STAGE_KEY, BACK=BACK)
        subprocess.run([str(TC / 'mn10300-elf-ld'), f'--section-start=.text={CODE_AT:#x}', '-e', '_start', str(t / 'o'),
                        '-o', str(t / 'e')] + [f'--defsym={k}={v:#x}' for k, v in syms.items()], check=True)
        subprocess.run([str(TC / 'mn10300-elf-objcopy'), '-O', 'binary', str(t / 'e'), str(t / 'b')], check=True)
        nm = subprocess.run([str(TC / 'mn10300-elf-nm'), str(t / 'e')], capture_output=True, text=True).stdout
        syms = {p[2]: int(p[0], 16) for p in (line.split() for line in nm.splitlines()) if len(p) == 3}
        return (t / 'b').read_bytes(), syms


def build():
    d = BIN.read_bytes()
    assert d[END_IMM - 2 - B:END_IMM + 4 - B] == b'\xfc\xcc' + struct.pack('<I', OLD_END), 'end-word stub changed'
    assert d[HOOK - B:HOOK + 7 - B] == HOOK_STOCK, 'converter entry changed'
    force = force_stage()
    code, syms = assemble(force)
    assert d[CODE_AT - B:CODE_AT + len(code) - B] == b'\xff' * len(code), 'code area not 0xFF'
    jump = b'\xdc' + struct.pack('<i', syms['hl_entry'] - HOOK) + b'\xcb\xcb'
    e = lambda a, old, new, why: dict(kind='0x100', addr=f'{a:#x}', expect=old.hex(), new=new.hex(), why=why)
    stage = f'stage fixed at {force} (TEST BUILD)' if force else 'stage from sid 961'
    edits = [
        e(END_IMM, d[END_IMM - B:END_IMM + 4 - B], struct.pack('<I', NEW_END),
          'halation: section 6 loaded end 0x612e7000 -> 0x61300000 (as space probe sp1)'),
        e(CODE_AT, d[CODE_AT - B:CODE_AT + len(code) - B], code, f'halation flag gate hl_flag ({len(code)} B, {stage})'),
        e(HOOK, HOOK_STOCK, jump, 'halation: flag converter entry -> hl_flag (jmp; nop; nop)'),
    ]
    (HERE / 'edits.json').write_text(json.dumps({'patch': 'halation', 'force_stage': force, 'edits': edits}, indent=1)
                                     + '\n')
    print(f'halation: hl_flag {len(code)} B at {CODE_AT:#x}, {stage}')


if __name__ == '__main__':
    build()
