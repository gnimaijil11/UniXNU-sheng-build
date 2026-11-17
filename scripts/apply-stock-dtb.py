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
        handle.seek(page)
        kernel = handle.read(kernel_size)
        handle.seek(page + (kernel_size + page - 1) // page * page)
        ramdisk = handle.read(ramdisk_size)
    return header, kernel, ramdisk, page


def collection(kernel):
    offset = kernel.find(MAGIC)
    if offset <= 0:
        raise SystemExit('no FDT magic in the kernel region')
    return offset, kernel[offset:]


def main():
    build, stock = sys.argv[1], sys.argv[2]
    header, kernel, ramdisk, page = parse(build)
    _, stock_kernel, _, _ = parse(stock)
    split, replacement = collection(kernel)
    _, received = collection(stock_kernel)
    new_kernel = kernel[:split] + received
    padded = (len(new_kernel) + page - 1) // page * page
    struct.pack_into('<I', header, 8, len(new_kernel))
    struct.pack_into('<I', header, 16, len(ramdisk))
    shutil.copyfile(build, build + '.mainline-dtb')
    tmp = build + '.tmp'
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
