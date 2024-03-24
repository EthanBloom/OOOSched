import csv
import sys
from collections import deque

#
def readinputs(filename):
    noop = ['R',0,0,0,0,0,0,0,0,0,0]
    insts = deque()
    #insts.append(noop)
    with open(filename) as csvfile:
        instreader=csv.reader(csvfile,delimiter=',')
        for row in instreader:
            # instruction formatting:
            '''
            inst-type, dest-reg, arg-1, arg-2, F, De, Re, Di, Is, WB, CMT
            '''
            if row[0] == 'R':
                insts.append([row[0],row[1],row[2],row[3],0,0,0,0,0,0,0])
            elif row[0] == 'L':
                insts.append([row[0],row[1],0,row[3],0,0,0,0,0,0,0])
            elif row[0] == 'I':
                insts.append([row[0],row[1],row[2],0,0,0,0,0,0,0,0])
            elif row[0] == 'S':
                insts.append([row[0],0,row[1],row[3],0,0,0,0,0,0,0])
            else: # first row (2 ints)
                PRFsize = int(row[0])
                MachineWidth = int(row[1])
    return insts, PRFsize, MachineWidth

#
def fetch(instructions: deque, fQue: deque, MachineWidth, cycle, PC):
    for i in range(MachineWidth):
        if len(instructions) > 0:
            inst = instructions.popleft()
            inst[4] = cycle
            inst.append(PC)
            fQue.append(inst)
            PC += 1
        i += 1
    return PC

#
def decode(fQue: deque, deQue: deque, MachineWidth, cycle):
    for i in range(MachineWidth):
        if len(fQue) > 0:
            inst = fQue.popleft()
            inst[5] = cycle
            deQue.append(inst)
        i += 1

# 
def rename(deQue: deque, reQue: deque, MachineWidth, cycle, MT, FL: deque):
    for i in range(MachineWidth):
        if len(deQue) > 0:
            inst = deQue.popleft()
            if inst[1] != 0 and len(FL) == 0:
                deQue.appendleft(inst)
                break
            inst.append(0)
            arg1 = inst[2]
            if arg1 != 0:
                inst[2] = MT[int(arg1)]     # rename arg1
            arg2 = inst[3]
            if arg2 != 0:
                inst[3] = MT[int(arg2)]     # rename arg2
            dest = inst[1]
            if dest != 0:           
                inst[12] = MT[int(dest)]    # keep track of old name for dest reg
                new_dest = FL.popleft()
                inst[1] = new_dest          # rename dest
                MT[int(dest)] = new_dest    # update MT
            inst[6] = cycle
            reQue.append(inst)
        i += 1

# 
def dispatch(IQ: list, ROB: deque, reQue: deque, LSQ: list, MachineWidth, cycle, RT: list):
    for i in range(MachineWidth):
        if len(reQue) > 0:
            inst = reQue.popleft()
            inst[2] = [inst[2], RT[inst[2]]]
            inst[3] = [inst[3], RT[inst[3]]]
            if inst[1] != 0:
                RT[inst[1]] = 0 # destination register is now not ready (unless no reg write i.e. store, branch)
            inst[7] = cycle
            inst.append(0)  # add flag for completion state
            IQ.append(inst)
            ROB.append(inst)
            if inst[0] == 'L' or inst[0] == 'S':
                LSQ.append(inst)
        i += 1

# 
def issue(IQ: list, ROB: deque, LSQ: list, MachineWidth, cycle, RT: list):
    wakeups = []
    for n in range(MachineWidth):
        if len(IQ) > 0:
            # Select Instruction Stage
            issued = False
            i = 0
            if (n + i) >= len(IQ):
                issued = True
            while not issued:
                inst = IQ[n + i]
                conflict = False
                if inst[2][1] == 1 and inst[3][1] == 1:
                    if inst[0] == 'R' or inst[0] == 'I':
                        issued = True
                    if inst[0] == 'L' or inst[0] == 'S':
                        for loadstore in LSQ:
                            if loadstore[0] == 'S' and inst != loadstore:
                                conflict = True
                            if inst == loadstore:
                                break
                        if not conflict:
                            issued = True

                if issued == True:
                    inst[8] = cycle
                    inst[13] = 1
                    wakeup_reg = inst[1]
                    wakeups.append(wakeup_reg)
                    RT[inst[1]] = 1
                
                i += 1
                if (n + i) >= len(IQ):
                    issued = True
            

        n += 1
    # Instruction Wakeup Stage
    for wakeup_reg in wakeups:
        for inst in IQ:
            if inst[2][0] == wakeup_reg or inst[3][0] == wakeup_reg:
                inst[2][1] = RT[inst[2][0]]
                inst[3][1] = RT[inst[3][0]]
        
#     
def writeback(IQ: list, ROB: deque, LSQ: list, MachineWidth, cycle):
    for n in range(MachineWidth):
        if len(ROB) > 0:
            wb = False
            i = 0
            for inst in IQ:
                if inst[13] == 1:
                    IQ.remove(inst)
                    if inst in LSQ:
                        LSQ.remove(inst)
            #if i >= len(ROB):
            while not wb:
                inst = ROB[i]
                if inst[13] == 1:
                    #if inst in LSQ:
                        #LSQ.remove(inst)
                    ROB[i][9] = cycle
                    ROB[i][13] = 2
                    wb = True
                    #IQ.remove(inst)
                else:
                    i += 1
                if i >= len(ROB):
                    wb = True
        n += 1

#     
def commit(ROB: deque, committedInsts: list, MachineWidth, FL: deque, cycle):
    to_free = []
    for i in range(MachineWidth):
        if len(ROB) > 0:
            if ROB[0][13] == 2:
                inst = ROB.popleft()
                inst[10] = cycle
                if inst[12] != 0:
                    to_free.append(inst[12]) # to be added to free list at next cycle
                committedInsts.append(inst)
        i += 1
    return to_free

# 
def simulate(instructions: deque, PRFsize, MachineWidth):
    # INITIALIZATION
    cycle=0
    PC = 0
    icount = len(instructions) - 1
    '''initialize structures for instrucrtions during in-order phase'''
    fQue = deque()
    deQue = deque()
    reQue = deque()
    committedInsts = []
    '''initialize other data structures'''
    IQ = []
    ROB = deque()
    LSQ = []
    FL = deque()
    for i in range(32, PRFsize):
        FL.append(i)
    to_free = []    # use for adding to free list after committment 
    MT = [i for i in range(32)]
    RT = [1 if i <= 32 else 0 for i in range(PRFsize)]

    # SIMULATION LOOP
    while len(committedInsts) < icount + 1:
        for reg in to_free:
            FL.append(reg)
        to_free = commit(ROB, committedInsts, MachineWidth, FL, cycle)
        writeback(IQ, ROB, LSQ, MachineWidth, cycle)
        issue(IQ, ROB, LSQ, MachineWidth, cycle, RT)
        dispatch(IQ, ROB, reQue, LSQ, MachineWidth, cycle, RT)
        rename(deQue, reQue, MachineWidth, cycle, MT, FL)
        decode(fQue, deQue, MachineWidth, cycle)
        PC = fetch(instructions, fQue, MachineWidth, cycle, PC)
        cycle = cycle + 1
    return committedInsts

#
def printcycles(instructions: list):
    for inst in instructions:
        for stage in range(4,10):
            print("{:d}".format(inst[stage]),end=",")
        print("{:d}".format(inst[10]))

#
def main():
    # TODO Uncomment next line for implementation. Comment following line after testing
    filename = sys.argv[1]
    #filename = "ex4.txt"
    instructions, PRFsize, MachineWidth = readinputs(filename)
    out = simulate(instructions, PRFsize, MachineWidth)
    printcycles(out)

if __name__ == "__main__":
    main()
