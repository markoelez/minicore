#!/usr/bin/env python3
import struct
from config import DRAM_SIZE

class DRAM:
    def __init__(self, size=DRAM_SIZE):
        self.size = size
        self.memory = b'\x00' * DRAM_SIZE

    def load(self, addr, size):
        mem = self.memory[addr : addr + size]
        return struct.unpack('<I', mem)[0]

    def store(self, addr, dat):
        self.memory = self.memory[:addr] + dat + self.memory[addr + len(dat):]
