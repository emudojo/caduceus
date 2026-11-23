# E-M1 II halation step 4: tinted halation pass

Status: in progress (2026-11-23). No camera available: every phase is emulator-proven; one camera build at the end.
Design source: E-P7 `patches/halation` (h1–h4) on the grain CPU route, docs/HALATION_RED.md §14–22, docs/GRAIN_PORT.md;
E-M1 II sites and harnesses: docs/OMD-EM1-II/HALATION.md (steps 2–3).

Route (as the E-P7 `gc_gs`): repoint the work-list word that pushes the Soft Focus blend setup (`mov imm32` operand at
`0x60393a6b` → `0x60398ee1`) to our wrapper. The wrapper runs the stock blend setup; if that returns with the blended
image in buffer 0x1000, it runs the halation pass on it, before the output pass. Data edit only on the stock side.

| Phase | Done when |
|---|---|
| 4a. Wrapper route | Blend setup on E-M1 shown synchronous (submit + wait) or the right completion point found; wrapper `hl_gs` emulated: stock result unchanged when halation is off, pass entry reached with job + record 0x1000 when on |
| 4b. Per-job decision | Wrapper decides from the job alone (stage, colour still, our forced 0x80 vs the user's Soft Focus); marker design proven not to collide with stock flag use |
| 4c. Neutral blend | Combiner 11/12 stubs (prototype `tools/emu_fixtures/em1_combiner_neutral.s`) gated by 4b: our forced jobs blend at w = 1024, user Soft Focus keeps 600 |
| 4d. Halation pass | E-P7 passes A/B/C ported to E-M1 services (malloc `0x600231fe`, lock/unlock, flush, mapper map from `emu_mapper`); bit-exact vs a Python model; guards (format 0x0302, size, malloc, mapper refusal) leave the image untouched |
| 4e. Tint and strength | Stage 1..3 → gmax; glow colour from the active look's tint (LOOKS.BIN +47), red by default |
| 4f. Control | Halo row in `color_creator_wheel` writing sid 961 (code moved to the 100 KB region) |
| 4g. Time budget | Pass time estimated against the 10 s watchdog (`0x6005aecc`); decide whether the timeout must change |
| 4h. Test release | Sealed with every check; camera test list |
