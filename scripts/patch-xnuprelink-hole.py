#!/usr/bin/env python3
"""Prefer the roomiest free run when placing the native __TEXT.

The caller maps __TEXT as whole 4 KiB pages below the next retained segment, so
a run that only just fits still loses its sub-page tail to the round-down. The
first-fit search can therefore fail by less than one page even though a larger
run exists further along __PRELINK_TEXT.
"""
import pathlib
import sys

OLD = '''        largest = 0
        for begin, end in sorted(self.occupied):
            if end <= cursor or begin >= limit:
                continue
            if align(cursor) + size <= begin:
                return align(cursor)
            largest = max(largest, begin - align(cursor))
            cursor = max(cursor, end)
        if align(cursor) + size <= limit:
            return align(cursor)
        largest = max(largest, limit - align(cursor))'''

NEW = '''        # Collect every run that fits and take the roomiest one: the caller maps
        # __TEXT as whole pages below the next retained segment, so a run that only
        # just fits loses its sub-page tail to the round-down and yields no room.
        candidates = []
        largest = 0
        for begin, end in sorted(self.occupied):
            if end <= cursor or begin >= limit:
                continue
            start = align(cursor)
            if start + size <= begin:
                candidates.append((begin - start, start))
            largest = max(largest, begin - start)
            cursor = max(cursor, end)
        start = align(cursor)
        if start + size <= limit:
            candidates.append((limit - start, start))
        largest = max(largest, limit - start)
        if candidates:
            return max(candidates)[1]'''


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    target = root / 'UniXNU/kits/XnuPrelink/fileset_layout.py'
    text = target.read_text()
    if NEW in text:
        print('xnu-prelink: roomiest-run placement already applied')
        return
    if text.count(OLD) != 1:
        raise SystemExit('xnu-prelink: hole() does not match; refusing to patch')
    target.write_text(text.replace(OLD, NEW, 1))
    print('xnu-prelink: hole() now returns the roomiest free run')


if __name__ == '__main__':
    main()
