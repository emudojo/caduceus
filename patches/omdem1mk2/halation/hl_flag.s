/* E-M1 Mark II halation step 3: Soft Focus flag gate for ordinary colour stills (docs/OMD-EM1-II/HALATION.md).
 *
 * Hooked at the entry of the Art Effect -> job-flag converter 0x6042285e (jmp + nop over its first 7 bytes).
 * There a0 = source request (+194 capture kind, +28 -> capture record) and a1 = the job-flag word. The caller's
 * `call ...,[a2,a3],20` already saved a2/a3, and the stock code overwrites both next, so they are free here.
 *
 * Gate (owner decisions, HALATION.md): the stage (sid 961, key 0xF709[0], 0..3; anything else = Off) is not Off,
 * the shot has no Art Effect (capture+24951 == 0, so the stock Soft Focus effect keeps its own route), the picture
 * mode (capture+24203, pipeline enum) is a colour mode: < 100 (no Art Filter) and not 5 (Monotone) or 12 (MONO),
 * as the stock mono test 0x60342c32; and the capture kind is not one the E-P7 skips (0x2001, 0x2006, 0x1008,
 * 0x1006). The converter's art-0 path preserves the added flag 0x80. The tested colour-still builder needs a
 * separate blend route (tools/omdem1mk2_emu_work_list.py). When the gate is closed, stock conversion proceeds.
 *
 * Built with FORCE_STAGE = 1..3 (as --defsym, test builds only) the stage is that constant instead of sid 961.
 */
.am33_2
.text
.global _start
_start:

hl_entry:
    mov a0,a3                 /* request */
    mov a1,a2                 /* flag word: the stock `mov a1,a2` */
    mov (28,a3),a0            /* capture record */
    movbu (24951,a0),d0       /* Art Effect */
    cmp 0,d0
    bne hl_done
    movbu (24203,a0),d0       /* picture mode */
    cmp 100,d0
    bcc hl_done               /* >= 100: Art Filter */
    cmp 5,d0
    beq hl_done               /* Monotone */
    cmp 12,d0
    beq hl_done               /* MONO profile mode */
    movhu (194,a3),d0         /* capture kind */
    cmp 0x2001,d0
    beq hl_done
    cmp 0x2006,d0
    beq hl_done
    cmp 0x1008,d0
    beq hl_done
    cmp 0x1006,d0
    beq hl_done
.if FORCE_STAGE
    mov FORCE_STAGE,d0
.else
    mov STAGE_KEY,d0          /* property getter(key, index 0, a0 = 0), as stock 0x604226d2 calls it */
    clr d1
    mov 0,a0
    call GETTER,[d2,d3],12
.endif
    cmp 0,d0
    beq hl_done
    cmp 3,d0
    bhi hl_done               /* SetValue does not range-check: anything above 3 (or negative) is Off */
    mov d0,d1                 /* job marker: params+31 -> job+35 = 0xA0 | (tint - 1) << 2 | stage (tint red for now) */
    or 0xa0,d1
    movbu d1,(19,a2)          /* a2 = params+12 */
    mov (a2),d0
    or 0x80,d0
    mov d0,(a2)
hl_done:
    mov (28,a3),a3            /* replay `mov (28,a0),a3` (a3 = request) */
    mov 24951,a1              /* replay `mov 24951,a1` */
    jmp BACK                  /* 0x60422865: `add a3,a1` */
