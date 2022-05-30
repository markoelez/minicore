import glob
from config import DRAM_SIZE, DRAM_BASE

def vaddr(addr):
    addr -= DRAM_BASE
    if addr < 0 or addr >= DRAM_SIZE:
        raise Exception(f'address {hex(addr)} is out of bounds!')
    return addr

def get_bits(dat, s, e):
    return (dat >> e) & ((1 << (s - e + 1)) - 1)

def sign_extend(x, b):
    if not x >> (b - 1):
        return x
    return -((1 << b) - x)

def load_tests():
    for x in glob.glob('tests/isa/rv32ui-p-*'):
        if x.endswith('.dump'):
            continue
        yield x
