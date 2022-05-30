#!/usr/bin/env python3
from elftools.elf.elffile import ELFFile
from registers import regnames, REGFILE
from ops import Ops, Funct3
from memory import DRAM
from config import DRAM_SIZE, DRAM_BASE
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

def step():

    # fetch
    ins = r32(regfile.pc)
    gb = lambda s, e : get_bits(ins, s, e)
    opcode = Ops(gb(6, 0))
    print(f'{hex(regfile.pc)}  {hex(ins):>10}  <{opcode}: {opcode.value}>')

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

            match funct3:
                case Funct3.ADD:
                    regfile[rd] = regfile[rs1] + imm
                case Funct3.SLLI:
                    regfile[rd] = regfile[rs1] << imm
                case Funct3.SRLI:
                    regfile[rd] = regfile[rs1] >> imm
                case Funct3.ORI:
                    regfile[rd] = regfile[rs1] | imm
                case Funct3.XOR:
                    regfile[rd] = regfile[rs1] ^ imm
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')

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
                case Funct3.BEQ:
                    cond = (regfile[rs1] == regfile[rs2])
                case Funct3.BNE:
                    cond = (regfile[rs1] != regfile[rs2])
                case Funct3.BLT:
                    cond = (regfile[rs1] < regfile[rs2])
                case Funct3.BGE:
                    cond = (regfile[rs1] >= regfile[rs2])
                case Funct3.OR:
                    cond = (regfile[rs1] | regfile[rs2])
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
            match funct3:
                case Funct3.ADD:
                    regfile[rd] = regfile[rs1] + regfile[rs2]
                case Funct3.AND:
                    regfile[rd] = regfile[rs1] & regfile[rs2]
                case Funct3.SRL:
                    regfile[rd] = regfile[rs1] >> regfile[rs2]
                case Funct3.SLT:
                    regfile[rd] = regfile[rs1] < regfile[rs2]
                case Funct3.SRL:
                    regfile[rd] = regfile[rs1] >> regfile[rs2]
                case Funct3.OR:
                    regfile[rd] = regfile[rs1] | regfile[rs2]
                case _:
                    print(regfile)
                    raise Exception(f'Unknown op for opcode: {opcode}, funct3: {funct3}')
        
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

    print(regfile)
    regfile.pc += 4
    return True

if __name__ == '__main__':
    for x in load_tests():
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
        
        #break
