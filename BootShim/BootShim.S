/* SPDX-License-Identifier: BSD-2-Clause-Patent
 *
 * BootShim: copies the UEFI FD to its base address, then an optional
 * XNUP payload to PAYLOAD_BASE, cleans the caches, and jumps to the FD.
 *
 * This is the upstream Mu-Silicium BootShim, matching the version used
 * by Jrorz/umi-mi10 (verified working on Mi 10, iOS 16.5 SpringBoard).
 *
 * FD_BASE, FD_SIZE, PAYLOAD_BASE are set via CFLAGS at compile time.
 */

_Head:
  adr   x1, _Payload          /* Set _Entry address */
  b     _Start

#if REQUIRES_KERNEL_HEADER == 1
_StackBase:
  .quad FD_BASE              /* Text Offset */
_StackSize:
  .quad FD_SIZE + (_Payload - _Head)  /* Complete shim + payload size */
  .quad 0                    /* Flags */
  .quad 0                    /* Reserved */
  .quad 0                    /* Reserved */
  .quad 0                    /* Reserved */
  .ascii "ARM\x64"           /* ARM64 Magic */
  .long 0                    /* Reserved */
#endif

_Start:
  mov   x4, x1
  ldr   x5, =FD_BASE
  cmp   x4, x5
  beq   _Entry
  ldr   x6, =FD_SIZE

_CopyLoop:
  ldp   x2, x3, [x4], #16
  stp   x2, x3, [x5], #16
  subs  x6, x6, #16
  b.ne  _CopyLoop

#ifdef PAYLOAD_BASE
  /* x4 now points just past the FD: an optional "XNUP" payload may follow */
  ldr   w2, [x4]
  movz  w3, #0x4E58
  movk  w3, #0x5055, lsl #16
  cmp   w2, w3
  b.ne  _NoPayload
  ldr   w6, [x4, #4]        /* Payload Size */
  add   x6, x6, #23         /* Header + Round Up to 16 */
  and   x6, x6, #~15
  movz  x5, #(PAYLOAD_BASE >> 16), lsl #16

_PayloadLoop:
  ldp   x2, x3, [x4], #16
  stp   x2, x3, [x5], #16
  subs  x6, x6, #16
  b.ne  _PayloadLoop

_NoPayload:
#endif
  ldr   x5, =FD_BASE

_Entry:
  /* Publish the copied instructions before executing them. */
  dsb   sy
  mrs   x9, ctr_el0
  ubfx  x9, x9, #16, #4
  mov   x10, #4
  lsl   x9, x10, x9
  sub   x10, x9, #1
  bic   x8, x5, x10
  ldr   x7, =FD_SIZE
  add   x7, x5, x7

_CleanLoop:
  dc    cvac, x8
  add   x8, x8, x9
  cmp   x8, x7
  b.lo  _CleanLoop
  dsb   sy
  ic    iallu
  dsb   sy
  isb
  br    x5

_Dead:
  b     _Dead

.text
.ltorg
.align 4

_Payload: