#!/usr/bin/env python3
import glob
import struct
from enum import Enum
from elftools.elf.elffile import ELFFile

DRAM_SIZE = 64 * (2 ** 10)  # 16 Kb
DRAM_BASE = 0x80000000

regnames = \
    ['x0', 'ra', 'sp', 'gp', 'tp'] + [f't{x}' for x in range(3)] + ['s0', 's1'] +\
    [f'a{x}' for x in range(8)] + \
    [f's{x}' for x in range(2, 12)] + \
    [f't{x}' for x in range(3, 7)] + ["PC"]

class Ops(Enum):
    LUI = 0b0110111 # load upper immediate
    LOAD = 0b0000011
    STORE = 0b0100011

    AUIPC = 0b0010111 # add upper immediate to pc
    BRANCH = 0b1100011
    JAL = 0b1101111
    JALR = 0b1100111

    IMM = 0b0010011
    OP = 0b0110011

    MISC = 0b0001111
    SYSTEM = 0b1110011

class Funct3(Enum):
    ADD = SUB = ADDI = 0b000
    SLLI = 0b001
    SLT = SLTI = 0b010
    SLTU = SLTIU = 0b011

    XOR = XORI = 0b100
    SRL = SRLI = SRA = SRAI = 0b101
    OR = ORI = 0b110
    AND = ANDI = 0b111

    BEQ = 0b000
    BNE = 0b001
    BLT = 0b100
    BGE = 0b101
    BLTU = 0b110
    BGEU = 0b111

    LB = SB = 0b000
    LH = SH = 0b001
    LW = SW = 0b010
    LBU = 0b100
    LHU = 0b101

    # stupid instructions below this line
    ECALL = 0b000
    CSRRW = 0b001
    CSRRS = 0b010
    CSRRC = 0b011
    CSRRWI = 0b101
    CSRRSI = 0b110
    CSRRCI = 0b111

def vaddr(addr):
    addr -= DRAM_BASE
    if addr < 0 or addr >= DRAM_SIZE:
        raise Exception(f'address {hex(addr)} is out of bounds!')
    return addr

class DRAM:
    def __init__(self, size=DRAM_SIZE):
        self.size = size
        self.memory = b'\x00' * DRAM_SIZE

    def load(self, addr, size):
        mem = self.memory[addr : addr + size]
        return struct.unpack('<I', mem)[0]

    def store(self, addr, dat):
        self.memory = self.memory[:addr] + dat + self.memory[addr + len(dat):]

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

memory = DRAM()
regfile = REGFILE()

def r32(addr):
    addr = vaddr(addr)
    return memory.load(addr, 4)

def reset():
    global memory, regfile
    memory = DRAM()
    regfile = REGFILE()

def get_bits(dat, s, e):
    return (dat >> e) & ((1 << (s - e + 1)) - 1)

def sign_extend(x, b):
    if not x >> (b - 1):
        return x
    return -((1 << b) - x)

def step():
    # fetch
    ins = r32(regfile.pc)
    opcode = Ops(get_bits(ins, 6, 0))
    print(f'{hex(regfile.pc)}  {hex(ins):>10}  <{opcode}: {opcode.value}>')

    match opcode:
        case Ops.JAL:
            # J-type instruction
            rd = get_bits(ins, 11, 7)
            imm = get_bits(ins, 31, 12)

            offset = (get_bits(ins, 32, 31) << 20 |
                (get_bits(ins, 30, 21) << 1) |
                (get_bits(ins, 21, 20) << 11) |
                (get_bits(ins, 19, 12) << 12))
            offset = sign_extend(offset, 21)
            
            regfile[rd] = regfile.pc + 4
            regfile.pc += offset
            return True

        case Ops.JALR:
            # I-type instruction
            rd = get_bits(ins, 11, 7)
            rs1 = get_bits(ins, 19, 15)
            imm = sign_extend(get_bits(ins, 31, 20), 12)
            
            regfile[rd] = regfile.pc + 4
            regfile.pc = regfile[rs1] + imm
            return True

        case Ops.IMM:
            # I-type instruction
            rd = get_bits(ins, 11, 7)
            rs1 = get_bits(ins, 19, 15)
            funct3 = Funct3(get_bits(ins, 14, 12))
            imm = sign_extend(get_bits(ins, 31, 20), 12)

            match funct3:
                case Funct3.ADD:
                    regfile[rd] = regfile[rs1] + imm
                case Funct3.SLLI:
                    regfile[rd] = regfile[rs1] << imm
                case Funct3.SRLI:
                    regfile[rd] = regfile[rs1] >> imm
                case Funct3.ORI:
                    regfile[rd] = regfile[rs1] | imm
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')

        case Ops.LUI:
            # U-type instruction
            rd = get_bits(ins, 11, 7)
            imm = get_bits(ins, 31, 12)
            regfile[rd] = imm << 12

        case Ops.AUIPC:
            # U-type instruction
            rd = get_bits(ins, 11, 7)
            imm = get_bits(ins, 31, 20)
            regfile[rd] = regfile.pc + imm

        case Ops.SYSTEM:
            funct3 = Funct3(get_bits(ins, 14, 12))
            rd = get_bits(ins, 11, 7)
            rs1 = get_bits(ins, 19, 15)
            csr = get_bits(ins, 31, 20)
            match funct3:
                case Funct3.CSRRS:
                    print('CSRRS', rd, rs1, csr)
                case Funct3.CSRRW:
                    print('CSRRW', rd, rs1, csr)
                    if csr == 3072:
                        return False
                case Funct3.CSRRWI:
                    print('CSRRWI', rd, rs1, csr)
                case Funct3.ECALL:
                    print('ECALL', rd, rs1, csr)
                    if regfile[3] == 21:
                        raise Exception('FAILURE')
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')

        case Ops.MISC:
            pass

        case Ops.BRANCH:
            # B-type instruction
            rs1 = get_bits(ins, 19, 15)
            rs2 = get_bits(ins, 24, 20)
            funct3 = Funct3(get_bits(ins, 14, 12))
            offset = (get_bits(ins, 32, 31) << 12 |
                (get_bits(ins, 30, 25) << 5) |
                (get_bits(ins, 11, 8) << 1) |
                (get_bits(ins, 8, 7) << 11))
            offset = sign_extend(offset, 13)

            cond = False
            match funct3:
                case Funct3.BEQ:
                    cond = (regfile[rs1] == regfile[rs2])
                case Funct3.BNE:
                    cond = (regfile[rs1] != regfile[rs2])
                case Funct3.BLT:
                    cond = (regfile[rs1] < regfile[rs2])
                case Funct3.BGE:
                    cond = (regfile[rs1] >= regfile[rs2])
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')
            if cond:
                regfile.pc += offset
                return True

        case Ops.OP:
            # R-type instruction
            rd = get_bits(ins, 11, 7)
            rs1 = get_bits(ins, 19, 15)
            rs2 = get_bits(ins, 24, 20)
            funct3 = Funct3(get_bits(ins, 14, 12))
            funct7 = get_bits(ins, 31, 25)
            match funct3:
                case Funct3.ADD:
                    regfile[rd] = regfile[rs1] + regfile[rs2]
                case Funct3.OR:
                    regfile[rd] = regfile[rs1] | regfile[rs2]
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')
        
        case Ops.STORE:
            # S-type instruction
            rs1 = get_bits(ins, 19, 15)
            rs2 = get_bits(ins, 24, 20)
            width = get_bits(ins, 14, 12)
            offset = sign_extend((get_bits(ins, 31, 25) << 5) | get_bits(ins, 11, 7), 12)

            addr = regfile[rs1] + offset
            dat = regfile[rs2]

            print('STORE: ', hex(addr), dat)

        case Ops.LOAD:
            # I-type instruction
            rd = get_bits(ins, 11, 7)
            rs1 = get_bits(ins, 19, 15)
            funct3 = Funct3(get_bits(ins, 14, 12))
            imm = sign_extend(get_bits(ins, 31, 20), 12)

            addr = regfile[rs1] + imm
            print('LOAD: ', hex(addr))

        case _:
            print(regfile)
            raise Exception(f'Unknown opcode: {opcode}')

    print(regfile)
    '''
    if hex(ins) == hex(0x7fff83b7):
        return False
    '''
        
    regfile.pc += 4
    return True

if __name__ == '__main__':
    for x in glob.glob('tests/isa/rv32ui-p-add*'):
        if x.endswith('.dump'):
            continue

        print(x) 
        # reset memory, registers
        reset()

        with open(x, 'rb') as f:
            e = ELFFile(f)
            for s in e.iter_segments():
                addr = vaddr(s.header.p_paddr)
                memory.store(addr, s.data())

            while step():
                pass
        
        break
