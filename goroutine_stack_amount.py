#!/usr/bin/python3

'''
goroutine_stack_amount.py module estimates a stack consumption for each
goroutine of a golang program (typically a daemon program).

Usage:
    Calculate stack amount for all functions of the target binary.
    $ objdump -d -M intel your-binary | ./stack_amount.py > stack_amount.tsv

    Take a goroutine profile using pprof.
    $ curl -s http://localhost:6060/debug/pprof/goroutine?debug=1 > goroutine.txt

    Get an estimated stack consumption.
    $ ./goroutine_stack_amount.py stack_amount.tsv goroutine.txt

This module prints like following:
    1 @ 0x42e01a 0x42e0ce 0x449b96 0x6d7e88 0x42dbc2 0x45aa41
    #	0x449b95	time.Sleep+0x165	stack:96
    #	0x6d7e87	main.main+0x47	stack:32
    #	0x42dbc1	runtime.main+0x211	stack:88
    total stack (estimated): 4096

Stack frames are separated by a blank line.

The first line of each stack frame looks like:
    N @ function addresses.
N means the number of goroutines having the same stack frame.

Middle lines may show 'stack:M', stack consumption of the function.

The last line prints an estimated stack consumption by all goroutines
having this stack frame. If sum of M < 4KiB, the result will be N * 4KiB.
'''

import argparse
from collections import namedtuple
import math
import re


FILE_HEADER = re.compile(r'^goroutine profile: total \d+$')
FRAME_HEADER = re.compile(r'^(\d+) @((?: 0x[0-9a-f]+)+)$')
LINE = re.compile(r'^#\t(0x[0-9a-f]+)\t(\S+)\t(.+)$')

Frame = namedtuple('Frame', ['count', 'pcs', 'detail'])
FrameDetail = namedtuple('FrameDetail', ['pc', 'pc_name', 'displacement', 'file_line'])


def split_pc_name_displacemnt(pc_name_displacement):
    elems = pc_name_displacement.split('+')
    if len(elems) == 2:
        disp = int(elems[1], base=16)
        return elems[0], disp
    if len(elems) == 1:
        return elems[0], None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stack_amount_tsv')
    parser.add_argument('goroutine_txt')

    ns = parser.parse_args()

    func_stack_amount = {}
    with open(ns.stack_amount_tsv) as f:
        for line in f:
            func_name, amount = line.split('\t')
            func_stack_amount[func_name] = int(amount.strip())

    with open(ns.goroutine_txt) as f:
        line = f.readline()
        m = FILE_HEADER.match(line)
        if not m:
            raise RuntimeError('unknown file format')

        waiting_frame = True
        frames = []
        for line in f:
            if line == '\n':
                waiting_frame = True
                continue

            m = FRAME_HEADER.match(line)
            if m:
                if not waiting_frame:
                    raise RuntimeError('unknown file format')
                waiting_frame = False
                frame = Frame(count=int(m.group(1)), pcs=m.group(2), detail=[])
                frames.append(frame)
                continue

            m = LINE.match(line)
            if m:
                if waiting_frame:
                    raise RuntimeError('unknown file format')
                pc_name, disp = split_pc_name_displacemnt(m.group(2))
                detail = FrameDetail(pc=int(m.group(1), base=16),
                                     pc_name=pc_name,
                                     displacement=disp,
                                     file_line=m.group(3))
                frames[-1].detail.append(detail)

    for frame in frames:
        print('{} @{}'.format(frame.count, frame.pcs))
        stack_amount_for_this_frame = 0
        for detail in frame.detail:
            stack_amount = func_stack_amount.get(detail.pc_name)
            print('#\t0x{:x}\t{}+0x{:x}\tstack:{}'.format(
                detail.pc, detail.pc_name, detail.displacement, stack_amount))
            if stack_amount is not None:
                stack_amount_for_this_frame += stack_amount

        if stack_amount_for_this_frame < 4 * 1024:
            stack_amount_for_this_frame = 4 * 1024
        pow2_amount = int(math.pow(2, math.ceil(math.log2(stack_amount_for_this_frame))))

        print('total stack (estimated): {}'.format(frame.count * pow2_amount))
        print()


if __name__ == '__main__':
    main()
