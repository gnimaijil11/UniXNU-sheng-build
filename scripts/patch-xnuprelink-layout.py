#!/usr/bin/env python3
"""Let the native __TEXT use the sub-page tail of its free run.

XnuPrelink places the native __TEXT in a free run inside __PRELINK_TEXT and then
maps it as whole 4 KiB pages below the next retained segment. The source-storage
runtime grows the segment past that whole-page limit while the run itself still
holds it: 0x1db3a8 needed against 0x1db000 usable pages. The round-down only
protects the next retained segment, and the run already ends there, so the run's
own tail is mine to use.

Two edits, both in fileset_layout.py:
  * hole()      -> return the roomiest free run instead of the first fit.
  * Layout.init -> map min(size, room) and report the sub-page tail it used.
"""
import pathlib
import sys

HOLE_OLD = '''        largest = 0
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

HOLE_NEW = '''        candidates = []
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

MAP_OLD = '''        self.mapped = {'__TEXT': min(self.segment('__TEXT')['size'], room // 0x1000 * 0x1000)}'''
MAP_NEW = '''        whole = room // 0x1000 * 0x1000
        # The round-down exists to keep clear of the next retained segment, which
        # bounds this run already; using the run's own sub-page tail is safe.
        self.mapped = {'__TEXT': min(self.segment('__TEXT')['size'], max(whole, min(room, used)))}
        if self.mapped['__TEXT'] > whole:
            print('xnu-prelink: __TEXT uses %#x bytes of sub-page tail above %#x'
                  % (self.mapped['__TEXT'] - whole, whole))'''


def patch(text, old, new, label, target):
    if new in text:
        print('xnu-prelink: %s already applied' % label)
        return text
    if text.count(old) != 1:
        raise SystemExit('xnu-prelink: %s does not match; refusing to patch' % label)
    print('xnu-prelink: %s applied' % label)
    return text.replace(old, new, 1)


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    target = root / 'UniXNU/kits/XnuPrelink/fileset_layout.py'
    text = target.read_text()
    text = patch(text, HOLE_OLD, HOLE_NEW, 'hole() roomiest run', target)
    text = patch(text, MAP_OLD, MAP_NEW, 'whole-page round-down relaxed', target)
    compile(text, str(target), 'exec')
    target.write_text(text)
    print('xnu-prelink: fileset_layout.py patched and syntax-checked')


if __name__ == '__main__':
    main()
