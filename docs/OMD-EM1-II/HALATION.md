# Halation on the OM-D E-M1 Mark II (fw 3.70): port plan

Status (2026-11-23). The flag gate and CPU pass have emulator coverage. Routing the pass for ordinary colour stills is
open. The design comes from the E-P7 halation in this repo (`patches/halation`,
`docs/HALATION_RED.md` §14–17, on `patches/bloom` + `patches/grain_cpu` r2). The OM-3 version
(androidfanman/caduceus-om3 v0.28, Apache-2.0, its own code after the E-P7 method) runs on different base firmware; only its
tuning is a candidate for later (h2: u = 255v/(v+K) tables, 3 + 10 two-layer blur, chroma weight from the cell's mean
brightness, gradual daylight fade; credit in NOTICE).

## Owner decisions (2026-11-13)

| Question | Decision |
|---|---|
| Scope | Halation applies **over any film / colour profile** once enabled, not per look |
| Where the setting lives | **A camera control, remembered over power-off** in the camera's own settings memory (one spare stock setting, found and emulator-proven first) |
| Picture modes | **All colour modes**: our looks (Color Creator) and the stock colour modes (Natural, Vivid, Muted, Portrait, i-Enhance, …). Not Monotone, not Art Filters |
| Precedence | **The global setting sets the strength; the glow colour comes from the look** (red / amber / warm / cool, `tint` at LOOKS.BIN record +47), red when the look has none |

## How "always applied" is guaranteed

1. **One global stage** (Off / Low / Med / High = gmax 0 / 112 / 176 / 240), read at each shot from its own setting. It is
   not in any look slot, so picking a film, a look or a picture mode cannot change or drop it.
2. The capture-flag hook adds the Soft Focus flag 0x80 when stage ≠ Off **and** the job is an ordinary still of a colour
   mode. Step 4a verifies where the firmware can use that flag to schedule the blend. The gate excludes the capture kinds the E-P7
   skips for grain (0x2001, 0x2006, 0x1008, 0x1006), Monotone, Art Filters (they keep their own flags), movies, live view.
   If the job already has 0x80 (e.g. a look with bloom), the halation pass runs after that blend as on the E-P7.
3. **Look values are only a fallback for the tint.** The E-P7's "0 = follow the look" stage is not used on this body.
4. **Emulator proof before any camera build** (AGENTS.md): run the flag hook and the pass entry with stage on/off for every
   picture-mode value, every look slot (built-in, card, none), card present / absent, each excluded capture kind, and
   bloom on/off; pass = the 0x80 flag and the pass call happen exactly when the rule above says, stock otherwise. The
   pass itself bit-exact against a Python model (as the OM-3 did).

## What has to exist first (E-P7 layers → E-M1 II)

| Layer | E-M1 II status (2026-11-13, byte search of the E-P7 sites) |
|---|---|
| Soft Focus route (bloom: flag hook, blend setup, combiner 11, callback) | callback `0x60391959`, blend setup `0x60398f5f`, effect selector `0x603f1653` exact; flag hook ≈ `0x604228fc`, Soft Focus entry ≈ `0x6039517c` / `0x60398ee1` (prefix match); combiner 11/12 calls not found by bytes |
| CPU pass route (grain_cpu r2: work-list hook, window / mapper, lock / unlock) | not found by bytes; needs code-shape search |
| Watchdog 10 s → 30 s (E-P7 v0.31b) | E-M1 II stock write path confirmed up to the hardware handshake. See below. |
| Spare remembered setting for the stage | **sid 961** (key `0xF709[0]`), see "Stage setting" below; power-off survival needs one camera test |
| Code space ~1.8 KB + tables; one malloc ≤ 16 KB per shot | 100 KB of loaded gap confirmed on camera with sp1. The actual halation allocation and code placement still need verification. |
| Camera control | a Halo row/page in the look editor (`color_creator_wheel`) |

## Step 1: code-space probe sp1 (2026-11-13; **camera: S+**)

- Gaps between loaded sections (loader `0x60042b96`, end getter `0x60042b35`, descriptor table `0x60027450`), scanned for
  code that uses an address inside them (`mov imm32` / absolute operands, cached and uncached): `0x605d3000` (8 KB),
  `0x6078f000` (28 KB), **`0x60bc8800..0x60bf1000` (162 KB)** and **`0x612e7000..0x61300000` (100 KB)** are referenced only
  by their section's end word; `0x60580800..` is written at runtime (`0xa05842f8`): not usable. The getter is called only by
  the loader. Base-region 0xFF runs are startup copy/clear ranges (`0x60021111`): not usable.
- sp1 raises **section 5's end word** (`0x60042b6d`) `0x612e7000 → 0x61300000`: the flash span then ends at section 6's own
  source (`0x4183f000`), so the loader copies the gap straight from the package. The gap holds a magic word + an LCG
  pattern; a 65-B check (`0x605d2f98`, section-3 tail, outside the probed region) sums it on each look-editor banner draw and
  appends **`S+`** (loaded, intact), **`S!`** (loaded, changed since boot) or **`S0`** (not loaded). Patch
  `patches/omdem1mk2/space_probe`; editor call only with `EM1_SPACE_PROBE=1`; `check_loaded` now reads the release's own
  end words.
- **Emulated** (`tools/omdem1mk2_emu_space.py`): end getter stock `0x612e7000` / patched `0x61300000`, flash span =
  section 6's source; the check on the built / 0xFF / one-word-changed region → `S+` / `S0` / `S!`, registers kept; the
  editor's own `call` site through the check and back. **Not emulated:** the loader's flash copy, and whether anything
  uses that RAM later -- that is the camera test.
- **Camera (owner, v0.4c13-sp1):** banner `Provia C0 S+ K0009+` after several bursts and picture-mode changes: the region is
  loaded and untouched by normal use → **0x612e7000..0x61300000 (100 KB) usable** for code and tables [C].
  The owner also reported `S+` after a power cycle and a movie.
- The 162 KB gap after section 4 can be probed the same way when needed.

## Step 2: E-M1 II sites (2026-11-20, static unless marked)

Full table and evidence: [`plans/reports/research-261120-1400-em1ii-softfocus-cpupass-sites.md`](../../plans/reports/research-261120-1400-em1ii-softfocus-cpupass-sites.md).
The E-P7 image was not available locally, so every match is from the E-P7 patch sources and docs, checked on the
E-M1 II disassembly.

- **Flag converter `0x6042285e`** (E-P7 `0x603eab39`): request +28 → capture; Art Effect byte capture+24951 → jump
  table `0x60556bfc` (1 → 0x80 Soft Focus, 2 → 0x400, 3 → 0x8000, 4 → 0x2000, 5 → 0x40, 6/7 → 0x100/0x200,
  8/9 → 0x800/0x1000); clears 0x4000 / 0x10000; sets 0x200000 from capture+24204 | +24205. **Emulated**
  (`tools/omdem1mk2_emu_artflags.py`, 160 cases, stock and v0.4c17; part of the release checks).
- **Flag hook `0x604228fc`**: stock `fa438c5ea000` (`movbu (24204,a3),d0; cmp 0,d0`), back at the `bne` `0x60422902`;
  a 6-byte `jmp d32; nop` fits as on the E-P7.
- **Soft Focus blend setup `0x60398ee1`.** The Art work-list builder loads its address from `0x60393a6b` under
  `btst 128` on job+16 at `0x603939ff`. The blend-setup hook `0x60398f5f` has the same 6 bytes as the E-P7. **Emulated**
  (`tools/omdem1mk2_emu_blend_setup.py`, entered with `calls` like a work-list item): finds records 0x1000 / 0x1061
  (bufidx), inits the request at **job+11364**, writes stage 0xf005 (+12) and effect 0x0402 (+656), copies both
  records to +20 / +84, describes the output at +340 (format 0x302, stride = width rounded up to 32, width, height) and
  queues it; the selector maps that request to combiner 11; at `0x60398f5f` a2 = request, a3 = record 0x1000; without
  record 0x1061 it returns 48 and writes nothing. Allocation, queue submit and release are frame-correct fixtures.
- **Gate design consequence:** the combiner stub gets ctx+4 = request = job+11364, so it can find the job itself
  (request − 11364) and test a per-job mark set by the flag hook, instead of a global flag that another job could see.
- **Combiners:** dispatcher `0x603dcd0c` (bank init, then `0x603dcd35`) → selector `0x603f1653` → table `0x6053e108`
  {id, handler}. For a kind-3 request the selector reads the effect code at **request+656**: 0x0402 → 11, 0x0403 → 12
  (effect table `0x6054c97c`, key = effect − 259). Combiner 11 `0x603dd06f` (word `0x6053e164`), 12 `0x603dd0b8` (word
  `0x6053e16c`); both write the bank at (ctx+8)+7364 and end in the shared tail `0x603dd518`. **No weight getter on
  this body:** 11/12 use the constants 600 / 424. **Emulated** (`tools/omdem1mk2_emu_combiner.py`): stock selects
  11/12 and writes +92 = 600|600<<16, +96 = 600, +136 = 424|424<<16, +140 = 424 (12 swapped). The neutral-blend design
  is proven with the prototype stubs `tools/emu_fixtures/em1_combiner_neutral.s` behind the two repointed table words
  (4-byte data edits): gate off = the stock bank byte for byte, gate on = w 1024 (11: A 1024 / B 0; 12: A 0 / B 1024)
  with every other bank word unchanged, combiners 9/10 untouched. The real gate (which job halation marked) is step 4.
  Lesson kept in the fixture: a helper the stub `call`s must have a non-zero frame (`[],4`), or its own nested `call`
  overwrites the return slot (the emulator caught this as an endless loop).
- **Capture kind [E]:** mapper `0x6042257f` (`tools/omdem1mk2_emu_capture_kind.py`): request+194 0x2001 / 0x2006 →
  type 0x110 / 0x120 (by request+206; 0x1000 if helper `0x60425e48` returns 1), 0x1008 / 0x1006 → 0, any other kind →
  0x1000. So the gate can test request+194 directly against the four excluded kinds, as on the E-P7.
- **CPU pass (grain_cpu r2):** bufidx `0x6038c01c`, lock/unlock `0x6006e9d0` / `0x6006ea19`, flush `0x60068709`,
  modeget/modeset `0x60068b78` / `0x60068b88`, malloc/free `0x600231fe` / `0x6002323d`.
- **Mapper `0x6006888f` [E]** (`tools/omdem1mk2_emu_mapper.py`, 144 cases, CPU ids 0..2). The E-P7 treated every
  address below 0xb0000000 as direct; this body differs:
  - **Refused, use directly:** addresses below 0x84000000 and 0xa0000000..0xafffffff. The mapper prints
    `[exad]change_addr_err!!` (`0x60023188`, a log, not a stop), returns 0 and does not lock.
  - **Windowed:** every other address. It locks (`0x6006e9d0`), flushes (`0x60068709`), maps the bucket holding the
    address (0x84..0x87 is 64 MB, the rest 128 MB) into this CPU's window and returns `0xb0000000 | (addr & 0x07ffffff)`
    (`0xb8000000 | …` for 0x98..0x9f and 0xf8..0xff). It writes the bucket code (0x1000, 0x2100, 0x3200, 0x7600,
    0x8700 … 0xfe00) into the window registers `0x98100058` / `0x9810004c` (+0x400 per CPU, low byte kept), stores a
    mode 0..11 in `0xa274d410[cpu]`, then unlocks with the lock's token.
  - **For the halation pass:** test the buffer address first; use refused-range addresses as they are, and call the
    mapper only for the others. One window per CPU at a time, so a pass that walks two buffers in different buckets
    must remap between them (or copy through a direct buffer). The Art work-list builder `0x60392e0d` writes items inline.
    Step 4a traces the separate colour-still builder.
- **Capture fields do not shift uniformly:** picture mode +24203, profile +24233 (+150 vs E-P7) but Art Effect +24951
  (+166). Capture kinds 0x2001 / 0x2006 / 0x1008 / 0x1006 appear unchanged in the kind mapper `0x6042257f`.
- Still open: Monotone's picture-mode value, the job key of stock colour modes, and the mapper's 0 return.

### Stage setting: sid 961 (2026-11-20)

Report: [`plans/reports/research-261120-1400-em1ii-spare-setting.md`](../../plans/reports/research-261120-1400-em1ii-spare-setting.md).

- **Sid 961, property key `0xF709` index 0** (E-P7 "sid − 2" mapping: COLOR1 highlight; this body never offers
  picture modes 11/12). The key appears nowhere in code; the sid number only as two log line numbers and one GUI
  resource id; it is in no descriptor, UI init table or editor list [S]. Validator lists −7..+7, default 0 = Off.
- **Persistence [S]:** all settings live in property block 90 (table `0x600a29b0`, RAM `0x624e2000`, registry
  `0xa2736c50`), shadowed to flash slots `0x40240000` / `0x40280000` ("fmem"). 961 is stored at `0x6250423a`.
  What triggers the flash write (power-off or periodic) is not traced.
- **Boot resets:** boot tail `0x601ac7cd` → store load `0x602daefb` → normal boot `0x602da762` (26-id list `0x604cd464`,
  or the 628-id list `0x604ce176` + custom-bank copy when sid 10052 ≠ 0) and boot reasons 7/9 `0x602da77a` (6-id
  list `0x604ce662`); reset primitive `0x602e5ba5`. 961 is in none of them. A full reset (1647-id list `0x604cd498`,
  or `0x602e5acc` when the store check fails) sets it to 0 = Off.
- **Emulated** (`tools/omdem1mk2_emu_spare_setting.py`): facade SetValue 0..3 → 0 and GetValue reads back; stored in
  block 90; kept through all three boot paths while control sid 267 is reset where its lists say.
- **Rules for the halation code:** SetValue does not range-check (7, 8, −8 are stored), so treat any value outside
  0..3 as Off. The value is the same in every shooting mode and is saved in custom modes (C1..), like Color Creator
  hue. Fallbacks: sid 981 (`0xF779[2]`, 0..3, default 1, one reader in the mode-12 mono branch) and 965.
- **Camera test needed:** set the stage, power off and on, read it back.

## Step 3: Soft Focus flag gate for colour stills (2026-11-20)

Patch `patches/omdem1mk2/halation` (`hl_flag.s`, `build.py`):

- **Code space:** section 6 loaded end `0x612e7000 → 0x61300000` (word `0x60042b6d`, the sp1 edit, camera S+); `hl_flag`
  (97 B) at `0x612e7000`.
- **Hook at the converter entry `0x6042285e`**, not at `0x604228fc`: at the entry a0 is still the request (capture kind
  at +194), later it is overwritten. The first 7 bytes (`mov (28,a0),a3; mov a1,a2; mov 24951,a1`, absolute, no branch
  lands inside) become `jmp hl_entry; nop; nop`; `hl_flag` replays them and returns to `0x60422865`.
- **Gate:** stage (sid 961 via the stock property getter `0x6005e6cf(0xF709, 0, a0 = 0)`, as stock `0x604226d2` calls
  it) is 1..3 (anything else Off), Art Effect byte capture+24951 = 0, picture mode capture+24203 < 100 and not 5
  (Monotone) or 12 (MONO) — the stock mono test `0x60342c32` returns 1 for 5, 12, 104 and 109/variant 2 — and the
  capture kind is not 0x2001 / 0x2006 / 0x1008 / 0x1006. Then flag 0x80 is ORed in; nothing else changes.
- This patch sets the Soft Focus flag. The step 4a capture-job test below shows that the class-0
  colour-still builder produces the same list with the flag set. The blend route for those jobs remains open.
- **Emulated** (`tools/omdem1mk2_emu_halation_flag.py`): the real settings store holds the stage in sid 961 (written
  through the facade), the patched converter reads it back; 1,260 runs over stage 0..3 / 7 × Art Effect × picture
  mode × capture kind × seed give exactly the stock flag word, plus 0x80 in the 36 gated cases. A build with the
  stage fixed (`EM1_HL_FORCE_STAGE`) passes with `--force-stage` and fails the sid-961 check, so the harness sees the
  stage. `emu_artflags` keeps the stock flag table for every Art Effect (gate off through Monotone).
- **Test release `v0.4c18t`** (stage fixed at 2 because no control sets sid 961 yet): `tools/omdem1mk2_catalog_release.py
  --version v0.4c18t` after `EM1_HL_FORCE_STAGE=2 python3 patches/omdem1mk2/halation/build.py`.
- For camera acceptance after routing is verified, Natural / Vivid / Color Creator stills show a soft glow with Halo
  enabled. Monotone, Art Filter, Art Effect, bursts, RAW+JPEG and movie are regression checks.

## Stock watchdog write path (2026-11-20)

The OM 3.70 stock path at `0x6005aecc` passes 10 to `0x600226fd`. The emulator ran that stock call with
mapped watchdog registers. It changed `0x98e0008c` from `0x13f` to `0x10a`, preserving the upper bits,
then wrote `0x20041001` to `0x98e000a4`. The run stopped before the hardware acknowledgement loop at
`0x60022728`. The startup path, timer units on camera, and time consumed by an E-M1 II image pass still
need confirmation before deciding whether to change the timeout.

## Order

1. Code space: confirmed with the sp1 loaded-end probe above.
2. Find the spare remembered setting and the Soft Focus / CPU-pass sites; emulator fixtures for the capture job.
   Sites: done (static, above). Emulated: flag converter, stage setting sid 961, capture-kind mapper, selector +
   combiner 11/12 with the neutral-blend stubs, blend setup, bus-address mapper. **Step 2 done.**
3. The step 3 flag gate is emulated in `v0.4c18t`. Complete the colour-still blend route before the glow camera test.
4. Halation pass with the global stage and gate above, then the camera control; emulator proof as in §"How", then camera.

## Step 4: tinted halation pass (in progress, 2026-11-23; plan `plans/261123-0838-em1ii-halation-step4/plan.md`)

- **Blend completion [S].** `0x60398ee1` submits at `0x60399008` (`0x60390536`), waits at `0x6039903d`
  (`0x60390293` → `0x603901f3`) and releases records at `0x60399048` / `0x60399053` before returning success.
  The standalone emulator fixture stubs the submit and wait services. `0x6039923c` also calls the body at
  `0x60398ee6` directly, outside the work-list immediate examined in 4a.
- **Work list (4a) [E].** `tools/omdem1mk2_emu_work_list.py` starts at the real capture entry `0x6041ec04`, follows
  the params fill `0x6041dda4` and lets constructor `0x6038f173` choose the builder. The request and capture input,
  heap allocations and logger are fixtures. The ordinary and Soft Focus-only cases reach publication at request+36.

  | Capture fixture | Work-list result |
  | --- | --- |
  | Vivid, Natural and Color Creator, kind `0x1000` / `0x1001`, class 0 | Stock flags `0` and `v0.4c18t` flags `0x80` both use builder `0x603a63f4` and publish identical lists: `0x603a5d7d`, `0x603a5d96`, `0x603a5df6`, `0x60391a9b`. |
  | Art Filter 101, Art Effect 0 | Flags `0x80`, builder `0x60392e0d`. After reduce `0x60398e6f`, the list has `0x6039905e` and `0x60391a9b`. Blend Setup remains pending in `a2` when the builder returns. |
  | Art Filter 101, Art Effect 2 | Flags `0x480`. At `0x60393b9c` the `0x400` branch writes the pending `0x60398ee1` into slot 3 (zero-based), at **job+11020**. The fixture stops after finalizing the primary list, before the secondary setup. |

  The list starts at job+10984 and each item is 12 B. The primary entry at item+0 is called by `0x6038fb5f`
  with `a0 = job`. The runner reached both the original entry and a redirected address after changing just the
  immediate at `0x60393a6b` in emulator memory. The callback dispatch at `0x60392765` uses item+4.
  The planned immediate edit is specific to the tested Art route. **4a still needs a route for ordinary colour
  stills** before `hl_gs` can be validated on those jobs.
- **Pass [E]:** `patches/omdem1mk2/halation/hl_pass.s` = the E-P7 h1/h2 passes A/B/C instruction for instruction, with the
  E-M1 bus guard (0xa0000000..0xafffffff direct; 0x84000000..0x9fffffff and 0xb0000000 up windowed; below 0x84000000
  refused), per-piece window open (lock, mode get, mapper, flush or mode restore, unlock) and the E-M1 allocators.
  `tools/omdem1mk2_emu_halation_pass.py`: 36 cases bit-exact with `tools/omdem1mk2_halation_model.py` (direct, windowed and
  a buffer crossing 0xd0000000, every stage × tint); daylight cap, no highlights, malloc failures, bad format and bad bus
  leave the photo untouched; locks == unlocks, frees balanced, the window mode restored.
- **Not yet:** the wrapper and per-job decision (4a/4b), combiner neutral blend (4c), look tint (4e), Halo control (4f),
  time budget vs the 10 s watchdog (4g). Nothing of step 4 is in a release.
- **Per-job marker (4b) [E, partial]:** the params block of each shot is a zeroed 32-byte stack local; the job constructor
  `0x6038f173` allocates a new 15,484-byte job and copies it word for word to job+4..+35 (`0x6038f2a4`), so params+N =
  job+4+N (job+8 request, job+16 flags). Marker = a magic byte hl_flag writes at params+31 → job+35 (combiner stub:
  request − 11329). `tools/omdem1mk2_emu_job_marker.py`: constructor and work-list builder give identical results with
  the byte 0 or 0xA5 except job+35 itself. Report: `plans/reports/research-261123-0838-em1ii-halation-job-marker.md`.
  Still to prove: the blend setup, combiners and destructor with the marker set, and the other three constructor paths.
