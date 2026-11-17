#!/usr/bin/env python3
"""Append the stock firmware DTB collection to a built sheng boot.img.

board.toml [bootimg] dtb points at build/sheng/sheng.dtb, the mainline device
tree (~140 KB, one blob). The stock ABL selects from the appended DTB table of
the vendor image instead (eight blobs, 450-530 KB each), and boots to a black
screen when only the mainline tree is present. Replace the appended collection
with the one from the stock firmware boot.img, keeping our own compressed
firmware and payload ramdisk untouched.

usage: apply-stock-dtb.py <built boot.img> <stock boot.img>
"""
import os
import shutil
import struct
import sys

MAGIC = b'\xd0\x0d\xfe\xed'


def parse(path):
    with open(path, 'rb') as handle:
        header = bytearray(handle.read(1660))
        if header[:8] != b'ANDROID!':
            raise SystemExit('%s: not an Android boot image' % path)
        kernel_size, = struct.unpack_from('<I', header, 8)
        ramdisk_size, = struct.unpack_from('<I', header, 16)
        page, = struct.unpack_from('<I', header, 36)
        if page == 0:
            # Android boot image v3/v4: no page_size field, no page padding, and the vendor
            # images carry their DTB in the dtbo partition instead of the boot image.
            raise SystemExit('%s: boot image v3/v4 (header_version %d) has no page_size and '
                             'carries no appended DTB; pass a DTB collection file instead'
                             % (path, struct.unpack_from('<I', header, 40)[0]))
        handle.seek(page)
        kernel = handle.read(kernel_size)
        handle.seek(page + (kernel_size + page - 1) // page * page)
        ramdisk = handle.read(ramdisk_size)
    return header, kernel, ramdisk, page


def load_stock(path):
    """Return the DTB collection to append.

    Accepts either a stock boot.img (collection follows the compressed firmware in its
    kernel region) or a raw collection file that already starts with an FDT.
    """
    with open(path, 'rb') as handle:
        magic = handle.read(4)
    if magic == MAGIC:
        with open(path, 'rb') as handle:
            return handle.read()
    _, stock_kernel, _, _ = parse(path)
    return collection(stock_kernel)[1]


def collection(kernel):
    offset = kernel.find(MAGIC)
    if offset <= 0:
        raise SystemExit('no FDT magic in the kernel region')
    return offset, kernel[offset:]


def main():
    build, stock = sys.argv[1], sys.argv[2]
    header, kernel, ramdisk, page = parse(build)
    split, _ = collection(kernel)
    received = load_stock(stock)
    if received[:4] != MAGIC:
        raise SystemExit('%s: stock input is not an FDT collection' % stock)
    new_kernel = kernel[:split] + received
    padded = (len(new_kernel) + page - 1) // page * page
    struct.pack_into('<I', header, 8, len(new_kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    shutil.copyfile(build, build + '.mainline-dtb')
    tmp = build + '.tmp'
    # The boot header is 1660 bytes but occupies a whole page; writing it unpadded shifts
    # every following region by (page - 1660) bytes and fails the layout check below.
    header += b'\0' * (page - len(header))
    with open(tmp, 'wb') as out:
        out.write(header)
        out.write(new_kernel)
        out.write(b'\0' * (padded - len(new_kernel)))
        out.write(ramdisk)
    total = os.path.getsize(tmp)
    expected = page + padded + len(ramdisk)
    if total != expected:
        raise SystemExit('layout check failed: %d != %d' % (total, expected))
    shutil.move(tmp, build)
    print('stock DTB collection: %d bytes; mainline tree replaced' % len(received))
    print('kernel region %d -> %d; boot.img %d bytes (page %d)'
          % (len(kernel), len(new_kernel), total, page))


if __name__ == '__main__':
    main()
