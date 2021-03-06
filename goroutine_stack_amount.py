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
    total stack (estimated): 2048

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
FRAME_HEADER = re.compile(r'^(?P<num>\d+) @(?P<pcs>[ x0-9a-f]+)$')

Frame = namedtuple('Frame', ['count', 'pcs'])
FuncAddrRange = namedtuple('FuncAddrRange', ['begin', 'end'])


def find_func(some_addr, func_addr_range):
    for func_name, addr_range in func_addr_range.items():
        if addr_range.begin <= some_addr <= addr_range.end:
            return func_name
    return None


def print_frame_stack_amount(frame, func_stack_amount, func_addr_range):
    print('{} @{}'.format(frame.count, frame.pcs))

    stack_amount_for_this_frame = 0
    for pc in frame.pcs.split():
        addr = int(pc, base=16)
        func_name = find_func(addr, func_addr_range)
        if not func_name:
            raise RuntimeError('failed to search', pc)

        stack_amount = func_stack_amount.get(func_name)
        print('#\t{}\t{}\tstack:{}'.format(
            pc, func_name, stack_amount))
        if stack_amount is not None:
            stack_amount_for_this_frame += stack_amount

    # stack default size == 2KiB
    # _StackMin constant defined in https://github.com/golang/go/blob/master/src/runtime/stack.go
    if stack_amount_for_this_frame < 2 * 1024:
        stack_amount_for_this_frame = 2 * 1024
    pow2_amount = int(math.pow(2, math.ceil(math.log2(stack_amount_for_this_frame))))

    print('total stack (estimated): {}'.format(frame.count * pow2_amount))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('stack_amount_tsv')
    parser.add_argument('goroutine_txt')

    ns = parser.parse_args()

    func_stack_amount = {}
    func_addr_range = {}
    with open(ns.stack_amount_tsv) as f:
        for line in f:
            func_name, addr_begin, addr_end, amount = line.split('\t')
            func_stack_amount[func_name] = int(amount.strip())
            func_addr_range[func_name] = FuncAddrRange(
                int(addr_begin, base=16),
                int(addr_end, base=16))

    with open(ns.goroutine_txt) as f:
        line = f.readline()
        m = FILE_HEADER.match(line)
        if not m:
            raise RuntimeError('unknown file format')

        frames = []
        for line in f:
            m = FRAME_HEADER.match(line)
            if not m:
                continue
            frame = Frame(count=int(m.group('num')), pcs=m.group('pcs'))
            frames.append(frame)

    for frame in frames:
        print_frame_stack_amount(frame, func_stack_amount, func_addr_range)
        print()


if __name__ == '__main__':
    main()
