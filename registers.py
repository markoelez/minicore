#!/usr/bin/env python3
from config import DRAM_BASE

regnames = \
    ['x0', 'ra', 'sp', 'gp', 'tp'] + [f't{x}' for x in range(3)] + ['s0', 's1'] +\
    [f'a{x}' for x in range(8)] + \
    [f's{x}' for x in range(2, 12)] + \
    [f't{x}' for x in range(3, 7)] + ["PC"]

class REGFILE:
    def __init__(self):
        self.num_regs = 32
        self.regs = [0] * (self.num_regs + 1)
        self.PC = 32
        self.regs[self.PC] = DRAM_BASE

    @property
    def pc(self):
        return self.regs[self.PC]

    @pc.setter
    def pc(self, val):
        self.regs[self.PC] = val

    def __getitem__(self, key):
        return self.regs[key]

    def __setitem__(self, key, value):
        if key == 0: return
        self.regs[key] = value & 0xFFFFFFFF

    def __repr__(self):
        res, lvl = [], []
        for i, r in enumerate(self.regs):
            if i != 0 and i % 8 == 0 or i == len(self.regs) - 1:
                res.append('\t'.join(lvl))
                lvl = []
            lvl.append(f'{regnames[i]:<2}: {r:08x}')
        res.append(f'PC : {self.regs[self.PC]:08x}')
        return '\n'.join(res)
