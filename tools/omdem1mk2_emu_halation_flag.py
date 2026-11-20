#!/usr/bin/env python3
"""Run the halation flag gate (patches/omdem1mk2/halation) through the real flag converter in the MN103 emulator.

    python3 tools/omdem1mk2_emu_halation_flag.py SPEC [--force-stage N]

SPEC is an edits.json that contains the halation edits (a release, or patches/omdem1mk2/halation/edits.json, which
is then applied alone). The settings store is the real one (tools/omdem1mk2_emu_spare_setting.py): the stage is
written to sid 961 through the facade, and hl_flag reads it back through the stock property getter 0x6005e6cf.
For every stage (0..3 and the out-of-range 7), Art Effect (0, 1 Soft Focus, 2), picture mode (Vivid 1, Natural 2,
Monotone 5, Color Creator 10, MONO 12, Art Filters 100 and 104), capture kind (0x1000, 0x1001, 0x2001, 0x2006, 0x1008,
0x1006) and two flag seeds, the patched converter must give exactly the stock flag word, plus 0x80 when the gate
holds: stage 1..3, Art Effect 0, picture mode < 100 and not 5 / 12, kind not in the four excluded. a2/a3/sp restored.
With --force-stage N (a test build) the stage is N whatever sid 961 holds.
"""
import argparse
import itertools
import json
import struct

import omdem1mk2_emu_spare_setting as S
import omdem1mk2_emu_validator as V
from penf_emulator import Region

CONVERTER = 0x6042285E
REQUEST, FLAGS, CAPTURE = 0x18030000, 0x18040000, 0x18100000
STAGES = (0, 1, 2, 3, 7)
ARTS = (0, 1, 2)
MODES = (1, 2, 5, 10, 12, 100, 104)
KINDS = (0x1000, 0x1001, 0x2001, 0x2006, 0x1008, 0x1006)
SEEDS = (0x00000000, 0x00214321)


def gate(stage, art, mode, kind):
    return 1 <= stage <= 3 and art == 0 and mode < 100 and mode not in (5, 12) and \
        kind not in (0x2001, 0x2006, 0x1008, 0x1006)


def convert(emu, art, mode, kind, seed):
    capture = bytearray(0x6200)
    capture[24951], capture[24203] = art, mode
    request = bytearray(0x100)
    struct.pack_into('<I', request, 28, CAPTURE)
    struct.pack_into('<H', request, 194, kind)
    extra = (Region('request', REQUEST, bytes(request), 'r'), Region('flags', FLAGS, struct.pack('<I', seed), 'rw', True),
             Region('capture', CAPTURE, bytes(capture), 'r'))
    regs = emu.call(CONVERTER, 0x30, 20, {'a0': REQUEST, 'a1': FLAGS, 'a2': 0x11112222, 'a3': 0x33334444}, extra)
    assert (regs['a2'], regs['a3'], regs['sp']) == (0x11112222, 0x33334444, V.SP), regs
    return struct.unpack('<I', emu.captured['flags'])[0]


def spec_with_release(path):
    """A patch-only spec is applied on top of the newest catalog release, as the release builder would."""
    spec = json.load(open(path))
    if 'camera' in spec:
        return path
    base = json.load(open(V.ROOT / 'releases/em1mk2/v0.4c17/edits.json'))
    base['edits'] = spec['edits'] + base['edits']
    out = '/tmp/halation_check_edits.json'
    json.dump(base, open(out, 'w'))
    return out


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('spec')
    p.add_argument('--force-stage', type=int, default=0)
    a = p.parse_args()
    stock, patched = S.Emu(None), S.Emu(spec_with_release(a.spec))
    cases = list(itertools.product(ARTS, MODES, KINDS, SEEDS))
    stock_flags = {case: convert(stock, *case) for case in cases}      # stock does not read the stage
    n = added = 0
    for stage in STAGES:
        assert patched.set_value(961, stage) == 0
        effective = a.force_stage or stage
        for case in cases:
            art, mode, kind, seed = case
            want = stock_flags[case]
            if gate(effective, art, mode, kind):
                want |= 0x80
                added += 1
            got = convert(patched, art, mode, kind, seed)
            assert got == want, (stage, art, mode, hex(kind), hex(seed), hex(got), hex(want))
            n += 1
    print(f'{n} converter runs: flags = stock exactly, plus 0x80 in the {added} gated cases '
          f'({"stage forced to %d" % a.force_stage if a.force_stage else "stage from sid 961"})')
    print('RESULT PASS')


if __name__ == '__main__':
    main()
