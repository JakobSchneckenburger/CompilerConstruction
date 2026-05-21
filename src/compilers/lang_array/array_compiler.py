from lang_array.array_astAtom import *
import lang_array.array_ast as plainAst
from lang_array.array_astCommon import *
from common.wasm import *
import lang_array.array_tychecker as array_tychecker
import lang_array.array_transform as array_transform
from lang_array.array_compilerSupport import *
from common.compilerSupport import *
#import common.utils as utils

def compileModule(m: plainAst.mod, cfg: CompilerConfig)-> WasmModule:
    """
    Compiles the given module.
    """
    vars = array_tychecker.tycheckModule(m)

    ctx = array_transform.Ctx()
    atomArray = array_transform.transStmts(m.stmts, ctx)

    instrs = compileStmts(atomArray, cfg)
    idMain = WasmId('$main')

    # declare locals for user variables
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x[0]), tyToWasmValType(x[1].ty)) for x in vars.items()]
    
    # @tmp_i32, @tmp_i64
    locals.extend(Locals.decls())
    
    # declare temporaries created during transformation (tmp_0, tmp_1, ...)
    for (ident, ty) in ctx.freshVars.items():
        locals.append((identToWasmId(ident), tyToWasmValType(ty)))

    return WasmModule(imports=wasmImports(cfg.maxMemSize), 
                      exports=[WasmExport("main", WasmExportFunc(idMain))],
                      globals=Globals.decls(),
                      data=Errors.data(),
                      funcTable=WasmFuncTable([]),
                      funcs=[WasmFunc(idMain, [], None, locals, instrs)])



def compileStmts(stmts: list[stmt], cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Compiles the given statements.
    """
    instrs: list[WasmInstr] = []
    for stmt in stmts:
        instrs += compileStmt(stmt, cfg)
    return instrs

def compileStmt(stmt: stmt, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Compiles the given statement.
    """
    match stmt:
        case StmtExp(e):
            instrs = compileExp(e, cfg)
            match e:
                case Call(Ident("print"), _):
                    return instrs
                case _:
                    return instrs + [WasmInstrDrop()]
                
            return instrs + [WasmInstrDrop()]
        case Assign(x, e):
            return (compileExp(e, cfg) + [WasmInstrVarLocal('set', identToWasmId(x))])
        case IfStmt(cond, thenBody, elseBody):
            instrs = compileExp(cond, cfg)
            instrs += [WasmInstrIf(None, compileStmts(thenBody, cfg), compileStmts(elseBody, cfg))]
            return instrs
        case WhileStmt(cond, body):
            instrs: list[WasmInstr]
            instrs = [
                WasmInstrBlock(
                    identToWasmId(Ident("loop_exit")), 
                    None, 
                    [
                        WasmInstrLoop(identToWasmId(Ident("loop_start")), 
                                      compileExp(cond, cfg) + [
                                          WasmInstrIf(
                                              None, 
                                              compileStmts(body, cfg) + [WasmInstrBranch(identToWasmId(Ident("loop_start")), False)], [WasmInstrBranch(identToWasmId(Ident("loop_exit")), False)])])
                    ]
                )
            ]
            return instrs
        case SubscriptAssign(arrayExp, indexExp, rightExp):
            instrs: list[WasmInstr] = []
            instrs += arrayOffsetInstrs(arrayExp, indexExp)
            instrs += compileExp(rightExp, cfg)
            instrs += [WasmInstrMem(tyToLiteral(tyOfExp(rightExp)), 'store')]
            #elemTy = tyOfExp(rightExp)
            #return (arrayOffsetInstrs(arrayExp, indexExp) + compileExp(rightExp, cfg) + [WasmInstrMem(tyToLiteral(elemTy), 'store')])
            return instrs

def compileExp(e: exp, cfg: CompilerConfig) -> list[WasmInstr]:
    """
    Compiles the given expression.
    """
    match e:
        #IntConst | Name | Call | UnOp | BinOp
        #case IntConst(value):
        #    return [WasmInstrConst('i64', value)]
        #case BoolConst(value):
        #    return [WasmInstrConst('i32', 1 if value else 0)]
        #case Name(name):
        #    return [WasmInstrVarLocal('get', identToWasmId(name))]
        case Call(name, args):
            instrs: list[WasmInstr] = []
            for arg in args:
                instrs += compileExp(arg, cfg)
            match name.name:
                case 'print':
                    match tyOfExp(args[0]):
                        case Int():
                            instrs += [WasmInstrCall(identToWasmId(Ident("print_i64")))]
                        case Bool():
                            instrs += [WasmInstrCall(identToWasmId(Ident("print_bool")))]
                        case _:
                            raise Exception(f'Unsupported type for print: {tyOfExp(args[0])}')
                case 'input_int':
                    instrs += [WasmInstrCall(identToWasmId(Ident("input_i64")))]
                case 'len':
                    instrs += arrayLenInstrs()
                case _:
                    instrs += [WasmInstrCall(identToWasmId(name))]
            return instrs
        case UnOp(op, arg):
            match op:
                case USub():
                    return ([WasmInstrConst('i64', 0)] + compileExp(arg, cfg) + [WasmInstrNumBinOp('i64', 'sub')])
                case Not():
                    return (compileExp(arg, cfg) + [WasmInstrConst('i32', 0)] + [WasmInstrIntRelOp('i32', 'eq')])
        case BinOp(left, op, right):
            instrs = compileExp(left, cfg)
            instrs += compileExp(right, cfg)
            match op:
                case Add():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrNumBinOp('i64', 'add')]
                case Sub():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrNumBinOp('i64', 'sub')]
                case Mul():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrNumBinOp('i64', 'mul')]
                case Less():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'lt_s')]
                case LessEq():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'le_s')]
                case Eq():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'eq')]
                case Greater():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'gt_s')]
                case GreaterEq():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'ge_s')]
                case NotEq():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'ne')]
                case And():
                    return compileExp(left, cfg) + [WasmInstrIf('i32', compileExp(right, cfg), [WasmInstrConst('i32', 0)])]
                case Or():
                    return compileExp(left, cfg) + [WasmInstrIf('i32', [WasmInstrConst('i32', 1)], compileExp(right, cfg))]
                case Is():
                    return compileExp(left, cfg) + compileExp(right, cfg) + [WasmInstrIntRelOp('i32', 'eq')]
        
        case ArrayInitDyn(lenExp, elemInit):
            elemTy = tyOfAtomExp(elemInit)
            
            instrs: list[WasmInstr] = []
            
            instrs += compileInitArray(lenExp, tyOfAtomExp(elemInit), cfg)
            
            #@tmp_i32arrayAddress
            instrs += [WasmInstrVarLocal('tee', identToWasmId(Ident('@tmp_i32')))]

            #@tmp_i32arrayAddress
            instrs += [WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32')))]

            instrs += [WasmInstrConst('i32', 4)]

            instrs += [WasmInstrNumBinOp('i32', 'add')]

            #@tmp_i32arrayElemAddress
            instrs += [WasmInstrVarLocal('set', identToWasmId(Ident('@tmp_i32')))]

            condition = [WasmInstrComment("Check if index is in range"), 
                         #@tmp_i32arrayElemAddress
                         WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))),
                         WasmInstrVarGlobal('get', identToWasmId(Ident("@free_ptr"))),
                         WasmInstrIntRelOp('i32', 'lt_u')] 
            
            IfBody: list[WasmInstr] = []
            
            IfBody = [WasmInstrComment("IfBody"),
                      WasmInstrComment("Initialize array elements"),
                      #@tmp_i32arrayElemAddress
                      WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))),
                      compileAtomExp(elemInit)[0],
                      WasmInstrMem(tyToLiteral(elemTy), 'store'),
                      WasmInstrComment("Increment element address"),
                      #@tmp_i32arrayElemAddress
                      WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32'))),
                      WasmInstrConst('i32', tySize(tyOfAtomExp(elemInit))),
                      WasmInstrNumBinOp('i32', 'add'),
                      #@tmp_i32arrayElemAddress
                      WasmInstrVarLocal('set', identToWasmId(Ident('@tmp_i32'))),
                      WasmInstrBranch(identToWasmId(Ident("loop_start")), False)]
            
            LoopBody: list[WasmInstr] = []

            LoopBody += condition + [WasmInstrIf(None, IfBody, [WasmInstrBranch(identToWasmId(Ident("loop_exit")), False)])]
            
            Loop: list[WasmInstr] = []

            Loop += [WasmInstrLoop(identToWasmId(Ident("loop_start")), LoopBody)]


            instrs += [
                WasmInstrBlock(
                    identToWasmId(Ident("loop_exit")), 
                    None, 
                    Loop
                )
            ]

            return instrs
        
        case ArrayInitStatic(elements):
            arrtype = tyOfExp(e)


            if not isinstance(arrtype, Array):
                raise Exception(f'Expected array type, got {arrtype}')
            
            elemTy = arrtype.elemTy
            
            instrs: list[WasmInstr] = []

            instrs = compileInitArray(IntConst(len(elements), Int()), elemTy, cfg)

            instrs += [WasmInstrComment("Initialize array elements")]

            #@tmp_i32arrayAddress
            instrs += [WasmInstrVarLocal('tee', identToWasmId(Ident('@tmp_i32')))]

            Offset = 0
            
            for elemInit in elements:
                elemTy = tyOfAtomExp(elemInit)

                #@tmp_i32arrayAddress
                instrs += [WasmInstrVarLocal('get', identToWasmId(Ident('@tmp_i32')))]

                instrs += [WasmInstrConst('i32', 4 + Offset)]

                instrs += [WasmInstrNumBinOp('i32', 'add')]

                instrs += compileAtomExp(elemInit)

                instrs += [WasmInstrMem(tyToLiteral(elemTy), 'store')]

                Offset += tySize(tyOfAtomExp(elemInit))


            return instrs
        case Subscript(arrayExp, indexExp):
            return arrayOffsetInstrs(arrayExp, indexExp) + [WasmInstrMem(tyToLiteral(tyOfExp(e)), 'load')]
        case AtomExp(atomexp):
            return compileAtomExp(atomexp)
                


def compileInitArray(lenExp: atomExp, elemTy: ty, cfg: CompilerConfig)-> list[WasmInstr]:
    instrs: list[WasmInstr] = []

    elemSize = tySize(elemTy)

    #instrs += [WasmInstrComment("Initialize array")]

    #-----------------------------------------------------
    # Compute the length of the array and store it in a local variable
    #-----------------------------------------------------

    instrs += [WasmInstrComment("initialize array length variable")]

    instrs = compileAtomExp(lenExp)

    #array_len
    instrs += [WasmInstrVarLocal('set', identToWasmId(Ident("@tmp_i64")))]

    #-----------------------------------------------------
    # Check array length is in range [0, cfg.maxArraySize]
    #-----------------------------------------------------

    instrs += [WasmInstrComment("Check array length is in Range")]

    instrs += [WasmInstrComment("Check array length is not too big")]

    #calculate the size of the array in bytes, array_len * elem_size + header_size(4 bytes)

    #array_len
    instrs += [WasmInstrVarLocal('get', identToWasmId(Ident("@tmp_i64")))]
    
    instrs += [WasmInstrConst('i64', elemSize)]
    
    instrs += [WasmInstrNumBinOp('i64', 'mul')]
    
    instrs += [WasmInstrConst('i64', 4)]
    
    instrs += [WasmInstrNumBinOp('i64', 'add')]
    
    instrs += [WasmInstrConst('i64', cfg.maxArraySize)]
    
    instrs += [WasmInstrIntRelOp('i64', 'gt_s')]

    #Error Size Too Big
    instrs += [WasmInstrIf(None,Errors.outputError(Errors.arraySize) + [WasmInstrTrap()], [])]

    instrs += [WasmInstrComment("Check array length is not negative")]

    #array_len
    instrs += [WasmInstrVarLocal('get', identToWasmId(Ident("@tmp_i64")))]

    instrs += [WasmInstrConst('i64', 0)]

    instrs += [WasmInstrIntRelOp('i64', 'lt_s')]

    #Array Size is Negative
    instrs += [WasmInstrIf(None,Errors.outputError(Errors.arraySize) + [WasmInstrTrap()], [])]

    #-----------------------------------------------------
    # Compute and store header
    #-----------------------------------------------------

    instrs += [WasmInstrComment("Compute and store header")]

    instrs += [WasmInstrVarGlobal('get', identToWasmId(Ident("@free_ptr")))]

    #array_len
    instrs += [WasmInstrVarLocal('get', identToWasmId(Ident("@tmp_i64")))]

    instrs += [WasmInstrConvOp('i32.wrap_i64')]

    instrs += [WasmInstrComment("shift left by 4, because bits 4-31 store the length")]

    instrs += [WasmInstrConst('i32', 4)]

    instrs += [WasmInstrNumBinOp('i32', 'shl')]

    instrs += [WasmInstrComment("set bit 0 to 1(garbage collector bit always 1)")]

    instrs += [WasmInstrConst('i32', 1)]

    instrs += [WasmInstrNumBinOp('i32', 'xor')]

    instrs += [WasmInstrMem('i32', 'store')]

    #-----------------------------------------------------
    # Update free pointer
    #-----------------------------------------------------

    instrs += [WasmInstrComment("Update free pointer")]

    instrs += [WasmInstrVarGlobal('get', identToWasmId(Ident("@free_ptr")))]

    #array_len
    instrs += [WasmInstrVarLocal('get', identToWasmId(Ident("@tmp_i64")))]

    instrs += [WasmInstrConvOp('i32.wrap_i64')]

    instrs += [WasmInstrComment("size of 1 element")]
    #size of elements
    instrs += [WasmInstrConst('i32', elemSize)]

    instrs += [WasmInstrNumBinOp('i32', 'mul')]

    instrs += [WasmInstrComment("size of header")]

    instrs += [WasmInstrConst('i32', 4)]

    instrs += [WasmInstrNumBinOp('i32', 'add')]

    instrs += [WasmInstrVarGlobal('get', identToWasmId(Ident("@free_ptr")))]

    instrs += [WasmInstrNumBinOp('i32', 'add')]

    instrs += [WasmInstrVarGlobal('set', identToWasmId(Ident("@free_ptr")))]


    return instrs

def compileAtomExp(exp: atomExp) -> list[WasmInstr]:
    instr: list[WasmInstr] = []
    match exp:
        case IntConst(value):
            instr += [WasmInstrConst('i64', value)]
            return instr
        case BoolConst(value):
            instr += [WasmInstrConst('i32', 1 if value else 0)]
            return instr
        case Name(name):
            instr += [WasmInstrVarLocal('get', identToWasmId(name))]
            return instr



def arrayLenInstrs()-> list[WasmInstr]:
    instrs: list[WasmInstr] = []

    instrs += [WasmInstrComment("Get array length, array address is on top of the stack")]

    instrs += [WasmInstrMem('i32', 'load')]

    instrs += [WasmInstrConst('i32', 4)]

    instrs += [WasmInstrNumBinOp('i32', 'shr_u')]

    instrs += [WasmInstrConvOp('i64.extend_i32_u')]

    return instrs

def arrayOffsetInstrs(arrayExp: atomExp, indexExp: atomExp)-> list[WasmInstr]:
    arrayTy = tyOfAtomExp(arrayExp)
    elemTy = arrayElemTy(arrayTy)
    elemSize = tySize(elemTy)

    instrs: list[WasmInstr] = []

    instrs += compileAtomExp(arrayExp)

    instrs += arrayLenInstrs()

    instrs += [WasmInstrComment("Check if Index is in range")]

    #array_len
    instrs += [WasmInstrVarLocal('set', identToWasmId(Ident("@tmp_i64")))]

    instrs += compileAtomExp(indexExp)

    #array_len
    instrs += [WasmInstrVarLocal('get', identToWasmId(Ident("@tmp_i64")))]

    instrs += [WasmInstrIntRelOp('i64', 'ge_s')]

    #Array Index is Too Big
    instrs += [WasmInstrIf(None,Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()], [])]

    instrs += compileAtomExp(indexExp)

    instrs += [WasmInstrConst('i64', 0)]

    instrs += [WasmInstrIntRelOp('i64', 'lt_s')]

    #Array Index is Negative
    instrs += [WasmInstrIf(None,Errors.outputError(Errors.arrayIndexOutOfBounds) + [WasmInstrTrap()], [])]

    instrs += [WasmInstrComment("Compute element address")]
    
    instrs += compileAtomExp(arrayExp)

    instrs += compileAtomExp(indexExp)

    instrs += [WasmInstrConvOp('i32.wrap_i64')]


    instrs += [WasmInstrConst('i32', elemSize)]

    instrs += [WasmInstrNumBinOp('i32', 'mul')]

    instrs += [WasmInstrConst('i32', 4)]

    instrs += [WasmInstrNumBinOp('i32', 'add')]

    instrs += [WasmInstrNumBinOp('i32', 'add')]


    return instrs






#---------------------------------------------------
# Helper functions for the compiler
#---------------------------------------------------

def identToWasmId(ident: ident) -> WasmId:
    return WasmId(f'${ident.name}')

def tyToWasmValType(t: ty) -> WasmValtype:
    match t:
        case Int():
            return 'i64'
        case Bool():
            return 'i32'
        case Array():
            return 'i32'
        case _:
            raise Exception(f'Unsupported type: {t}')
        
def tyToLiteral(t: ty) -> Literal['i32', 'i64']:
    match t:
        case Int():
            return 'i64'
        case Bool():
            return 'i32'
        case Array():
            return 'i32'
        
def tyOfExp(e: exp)-> ty:
    if e.ty is None:
        raise Exception("Expression has no type")
    elif isinstance(e.ty, Void):
        raise Exception("Expression has void type")
    else:
        return e.ty.ty
    
def tyOfAtomExp(e: atomExp)-> ty:
    if e.ty is None:
        raise Exception("Expression has no type")
    elif isinstance(e.ty, Void):
        raise Exception("Expression has void type")
    else:
        return e.ty
    
def tySize(t: ty) -> int:
    match t:
        case Int():
            return 8
        case Bool():
            return 4
        case Array():
            return 4

def arrayElemTy(t: ty) -> ty:
    match t:
        case Array(elemTy):
            return elemTy
        case _:
            raise Exception(f'Expected array type, got {t}')