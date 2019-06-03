#!/usr/bin/python3

'''
stack_amount.py module calculates stack consumptions for all functions,
using disassembled codes obtained by objdump.

Usage:
    $ objdump -d -M intel your-binary | ./stack_amount.py
'''

from collections import namedtuple, defaultdict
import re
import sys


# 00000000007d2850 <type..eq.[3]os.Signal>:
FUNC_LABEL = re.compile(r'^(?P<addr>[0-9a-f]+)\s*<(?P<name>[^>]*)>:$')
#   402798:       48 83 ec 08             sub    rsp,0x8
SUB_RSP = re.compile(r'^sub\s+rsp,*([0-9a-fx]*)')


SubRsp = namedtuple('SubRsp', ['line', 'amount'])
Push = namedtuple('Push', ['line'])

FuncAddrRange = namedtuple('FuncAddrRange', ['begin', 'end'])


def calc_stack_amount(ops: list) ->int:
    '''calc_stack_amount returns the total amount of stacks
    consumed by operations in ops.

    Args:
        ops: A list of SubRsp or Push.

    Returns:
        The total amount of stacks (in bytes) consumed by ops.
    '''
    amount = 8
    for op in ops:
        if isinstance(op, SubRsp):
            amount += op.amount
        elif isinstance(op, Push):
            amount += 8
    return amount


def extract_op(op_str: str):
    '''extract_op returns one of operations, or None.

    Args:
        op_str: An assembly line, like 'sub  rsp,0x10'

    Returns:
        One of SubRsp, Push, None corresponding to op_str.
    '''
    if op_str.startswith('sub'):
        m = SUB_RSP.match(op_str)
        if m:
            return SubRsp(line=op_str, amount=int(m.group(1), base=16))
    elif op_str.startswith('push '):
        return Push(line=op_str)
    return None


def print_func_stack_larger(func_ops: dict, func_addr_range: dict):
    '''print_func_stack_larger prints function name and stack consumption
    for each functions containd in func_ops.
    Each line will contain one function name, function address range,
    and the stack consumption separated by a tab (\t).
    '''
    func_stack_larger = sorted(
        ((name, calc_stack_amount(ops)) for name, ops in func_ops.items()),
        key=lambda x: x[1],
        reverse=True)
    for func_name, amount in func_stack_larger:
        addr_range = func_addr_range.get(func_name)
        if addr_range:
            print('{}\t{:x}\t{:x}\t{}'.format(
                func_name, addr_range.begin, addr_range.end, amount))


def main():
    func_ops = dict()

    func_addr_range = dict()
    func_name = None

    next_line = sys.stdin.readline()
    line = next_line
    while line:
        line = next_line
        next_line = sys.stdin.readline()

        if func_name is None:
            m = FUNC_LABEL.match(line)
            if m:
                func_name = m.group('name')
                func_addr = int(m.group('addr'), base=16)
                func_ops[func_name] = list()
            continue

        elems = line.split('\t')
        if len(elems) != 3:
            continue

        if next_line == '\n' or next_line == '':
            # disassemble looks like:
            #  7eda0d:	c3    	ret    
            if not elems[0].endswith(':'):
                raise RuntimeError('unknown address format')
            func_end_addr = int(elems[0][:-1], base=16)
            func_addr_range[func_name] = FuncAddrRange(func_addr, func_end_addr)

            func_name = None
            continue

        op = extract_op(elems[2])
        if op is not None:
            func_ops[func_name].append(op)

    print_func_stack_larger(func_ops, func_addr_range)


if __name__ == '__main__':
    main()
