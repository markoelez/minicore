#!/usr/bin/env python3
from elftools.elf.elffile import ELFFile
from registers import regnames, REGFILE
from ops import Ops, Funct3
from memory import DRAM
from config import DRAM_SIZE, DRAM_BASE, XLEN, BM
from util import vaddr, get_bits, sign_extend, load_tests

memory = DRAM()
regfile = REGFILE()

def r32(addr):
    addr = vaddr(addr)
    return memory.load(addr, 4)

def reset():
    global memory, regfile
    memory = DRAM()
    regfile = REGFILE()

def arith(funct3, x, y):
    match funct3:
        case Funct3.ADD:
            return x + y
        case Funct3.AND:
            return x & y
        case Funct3.SRLI:
            return x >> y
        case Funct3.SLLI:
            return x << y
        case Funct3.SLT:
            return int(sign_extend(x, 32) < sign_extend(y, 32))
        case Funct3.SLTU:
            return int(x < y)
        case Funct3.OR:
            return x | y
        case Funct3.XOR:
            return x ^ y
        case _:
            print(regfile)
            raise Exception(f'Unknown op for funct3: {funct3}')

def step():

    # fetch
    ins = r32(regfile.pc)
    gb = lambda s, e : get_bits(ins, s, e)
    opcode = Ops(gb(6, 0))
    #print(f'{hex(regfile.pc)}  {hex(ins):>10}  <{opcode}: {opcode.value}>')

    match opcode:
        case Ops.JAL:
            # J-type instruction
            rd = gb(11, 7)
            imm = gb(31, 12)

            offset = (gb(32, 31) << 20 |
                (gb(30, 21) << 1) |
                (gb(21, 20) << 11) |
                (gb(19, 12) << 12))
            offset = sign_extend(offset, 21)
            
            regfile[rd] = regfile.pc + 4
            regfile.pc += offset
            return True

        case Ops.JALR:
            # I-type instruction
            rd = gb(11, 7)
            rs1 = gb(19, 15)
            imm = sign_extend(gb(31, 20), 12)
            
            regfile[rd] = regfile.pc + 4
            regfile.pc = regfile[rs1] + imm
            return True

        case Ops.IMM:
            # I-type instruction
            rd = gb(11, 7)
            rs1 = gb(19, 15)
            funct3 = Funct3(gb(14, 12))
            imm = sign_extend(gb(31, 20), 12)
            funct7 = gb(31, 25)

            if funct3 == Funct3.SRAI and funct7 == 0b0100000:
                # SRAI
                sb = regfile[rs1] >> (XLEN - 1)
                out = regfile[rs1] >> gb(24, 20)
                out |= (BM * sb) << (XLEN - gb(24, 20))
                regfile[rd] = out
            else:
                # SLLI/SRLI
                regfile[rd] = arith(funct3, regfile[rs1], imm)

        case Ops.LUI:
            # U-type instruction
            rd = gb(11, 7)
            imm = gb(31, 12)
            regfile[rd] = imm << 12

        case Ops.AUIPC:
            # U-type instruction
            rd = gb(11, 7)
            imm = gb(31, 20)
            regfile[rd] = regfile.pc + imm

        case Ops.SYSTEM:
            funct3 = Funct3(gb(14, 12))
            rd = gb(11, 7)
            rs1 = gb(19, 15)
            csr = gb(31, 20)
            match funct3:
                case Funct3.CSRRS:
                    #print('CSRRS', rd, rs1, csr)
                    pass
                case Funct3.CSRRW:
                    #print('CSRRW', rd, rs1, csr)
                    pass
                    if csr == 3072:
                        print('SUCCESS')
                        return False
                case Funct3.CSRRWI:
                    #print('CSRRWI', rd, rs1, csr)
                    pass
                case Funct3.ECALL:
                    #print('ECALL', rd, rs1, csr)
                    if regfile[3] > 1:
                        raise Exception('FAILURE')
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')

        case Ops.MISC:
            pass

        case Ops.BRANCH:
            # B-type instruction
            rs1 = gb(19, 15)
            rs2 = gb(24, 20)
            funct3 = Funct3(gb(14, 12))
            offset = (gb(32, 31) << 12 |
                (gb(30, 25) << 5) |
                (gb(11, 8) << 1) |
                (gb(8, 7) << 11))
            offset = sign_extend(offset, 13)

            cond = False
            match funct3:
                case Funct3.AND:
                    cond = sign_extend(regfile[rs1], 32) & sign_extend(regfile[rs2], 32)
                case Funct3.BEQ:
                    cond = sign_extend(regfile[rs1], 32) == sign_extend(regfile[rs2], 32)
                case Funct3.BNE:
                    cond = sign_extend(regfile[rs1], 32) != sign_extend(regfile[rs2], 32)
                case Funct3.BLT:
                    cond = sign_extend(regfile[rs1], 32) < sign_extend(regfile[rs2], 32)
                case Funct3.BLTU:
                    cond = regfile[rs1] < regfile[rs2]
                case Funct3.BGE:
                    cond = sign_extend(regfile[rs1], 32) >= sign_extend(regfile[rs2], 32)
                case Funct3.OR:
                    cond = sign_extend(regfile[rs1], 32) | sign_extend(regfile[rs2], 32)
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')
            if cond:
                regfile.pc += offset
                return True

        case Ops.OP:
            # R-type instruction
            rd = gb(11, 7)
            rs1 = gb(19, 15)
            rs2 = gb(24, 20)
            funct3 = Funct3(gb(14, 12))
            funct7 = gb(31, 25)

            if funct3 == funct3.SUB and funct7 == 0b0100000:
                # sub
                regfile[rd] = regfile[rs1] - regfile[rs2]
            else:
                # add
                regfile[rd] = arith(funct3, regfile[rs1], regfile[rs2])
        
        case Ops.STORE:
            # S-type instruction
            rs1 = gb(19, 15)
            rs2 = gb(24, 20)
            width = gb(14, 12)
            offset = sign_extend((gb(31, 25) << 5) | gb(11, 7), 12)

            addr = regfile[rs1] + offset
            dat = regfile[rs2]

            print('STORE: ', hex(addr), dat)

        case Ops.LOAD:
            # I-type instruction
            rd = gb(11, 7)
            rs1 = gb(19, 15)
            funct3 = Funct3(gb(14, 12))
            imm = sign_extend(gb(31, 20), 12)

            addr = regfile[rs1] + imm
            print('LOAD: ', hex(addr))

        case _:
            print(regfile)
            raise Exception(f'Unknown opcode: {opcode}')

    #print(regfile)
    regfile.pc += 4
    return True

if __name__ == '__main__':
    for x in load_tests():
        
        if 'fence_i' in x or '-sh' in x:
            continue # TODO: fix

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
