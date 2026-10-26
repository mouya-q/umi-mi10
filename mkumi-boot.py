#!/usr/bin/env python3
"""
Pack the umi UEFI (with the XNU loader payload) into an Android boot image
for Xiaomi Mi 10 (umi / SM8250 / Kona).

Matches the Jrorz/umi-mi10 verified working configuration:
  - header_version = 1
  - append_dtb = true (DTB appended to gzip'd kernel blob)
  - Uses mkbootimg.py (from Mu-Silicium Resources/Scripts)

  kernel = gzip(BootShim + UEFI_FD + ["XNUP" container]) + DTB

The BootShim copies the FD to FD_BASE and the payload to PAYLOAD_BASE.

For TWRP flash (persistent boot partition):
  page_size = 4096, base = 0x0 (matching Mi 10 stock boot image)
"""
import argparse, gzip, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
PREBUILT = os.path.join(HERE, 'prebuilt', 'uefi')

def env_int(name, default):
    v = os.environ.get(name, '')
    return int(v, 0) if v else default

FD_BASE = env_int('FD_BASE', 0x9FC00000)
FD_SIZE = env_int('FD_SIZE', 0x300000)
PAYLOAD_BASE = env_int('PAYLOAD_BASE', 0xF0000000)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('-p', '--payload', help='XNUP payload file (USB loader)')
    ap.add_argument('-o', '--output', default='out/umi-boot.img')
    ap.add_argument('--shim', default=os.path.join(HERE, 'BootShim', 'BootShim.bin'))
    ap.add_argument('--fd', default=os.environ.get('UEFI_FD', os.path.join(PREBUILT, 'SILICIUM_UEFI.fd')))
    ap.add_argument('--dtb', default=os.environ.get('DTB', os.path.join(HERE, 'uefi/files/Resources/DTBs/umi.dtb')))
    ap.add_argument('--ramdisk', default=os.path.join(PREBUILT, 'ramdisk'))
    ap.add_argument('--mkbootimg', default=os.path.join(HERE, 'prebuilt', 'uefi', 'mkbootimg.py'))
    ap.add_argument('--no-gzip', action='store_true', help='Do not gzip-compress kernel')
    ap.add_argument('--pagesize', type=lambda x: int(x, 0), default=4096,
                    help='Page size for boot image (default 4096 for TWRP flash)')
    ap.add_argument('--base', type=lambda x: int(x, 0), default=0x0,
                    help='Base address (default 0x0 for Mi 10)')
    ap.add_argument('--header_version', type=lambda x: int(x, 0), default=1,
                    help='Boot image header version (default 1)')
    ap.add_argument('--cmdline', default='',
                    help='Kernel command line')
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.output) or '.', exist_ok=True)

    # Read components
    shim = open(args.shim, 'rb').read()
    fd = open(args.fd, 'rb').read()
    assert len(fd) == FD_SIZE, f'FD size mismatch: {len(fd)} != {FD_SIZE:#x}'

    # Build kernel blob: BootShim + UEFI_FD + optional XNUP payload
    blob = shim + fd
    if args.payload:
        payload = open(args.payload, 'rb').read()
        assert payload[:4] == b'XNUP', 'Payload must be XNUP container'
        assert len(payload) <= 0x04000000 - 0x1000, 'Payload too large'
        blob += payload
        blob += b'\x00' * (-len(blob) % 16)
        print(f'payload: {len(payload)} bytes')

    # Gzip compress the kernel blob
    if args.no_gzip:
        kernel_data = blob
        print(f'kernel (uncompressed): {len(kernel_data)} bytes')
    else:
        kernel_data = gzip.compress(blob, 6)
        print(f'kernel (gzip): {len(kernel_data)} bytes (uncompressed: {len(blob)})')

    # Append DTB to the kernel (append_dtb=true, v1 format)
    dtb = open(args.dtb, 'rb').read()
    kernel = kernel_data + dtb
    print(f'kernel+dtb: {len(kernel)} bytes (kernel {len(kernel_data)} + dtb {len(dtb)})')

    # Write the combined kernel to a temp file
    kernel_file = args.output + '.kernel~'
    with open(kernel_file, 'wb') as f:
        f.write(kernel)

    try:
        cmd = [
            sys.executable, args.mkbootimg,
            '--kernel', kernel_file,
            '--ramdisk', args.ramdisk,
            '--header_version', str(args.header_version),
            '--pagesize', str(args.pagesize),
            '--base', str(args.base),
            '-o', args.output,
        ]
        if args.cmdline:
            cmd += ['--cmdline', args.cmdline]
        print(f'Running: {" ".join(cmd)}')
        subprocess.check_call(cmd)
    finally:
        os.unlink(kernel_file)

    size = os.path.getsize(args.output)
    print(f'{args.output}: {size} bytes (shim {len(shim)}, uncompressed {len(blob)})')

if __name__ == '__main__':
    main()