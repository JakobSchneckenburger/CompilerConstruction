from lang_loop.loop_ast import *
from common.wasm import *
import lang_loop.loop_tychecker as loop_tychecker
from common.compilerSupport import *
#import common.utils as utils

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = loop_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x[0]), tyToWasmValType(x[1].ty)) for x in vars.items()]
    return WasmModule(imports=wasmImports(cfg.maxMemSize), 
                      exports=[WasmExport("main", WasmExportFunc(idMain))],
                      globals=[],
                      data=[],
                      funcTable=WasmFuncTable([]),
                      funcs=[WasmFunc(idMain, [], None, locals, instrs)])
    #locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64') for x in vars]
    #return WasmModule(imports=wasmImports(cfg.maxMemSize), 
    #                  exports=[WasmExport("main", WasmExportFunc(idMain))],
    #                  globals=[],
    #                  data=[],
    #                  funcTable=WasmFuncTable([]),
    #                  funcs=[WasmFunc(idMain, [], None, locals, instrs)])


def compileStmts(stmts: list[stmt]) -> list[WasmInstr]:
    """
    Compiles the given statements.
    """
    instrs: list[WasmInstr] = []
    for stmt in stmts:
        instrs += compileStmt(stmt)
    return instrs

def compileStmt(stmt: stmt) -> list[WasmInstr]:
    """
    Compiles the given statement.
    """
    match stmt:
        case StmtExp(e):
            instrs = compileExp(e)
            match e:
                case Call(Ident("print"), _):
                    return instrs
                case _:
                    return instrs + [WasmInstrDrop()]
                
            return instrs + [WasmInstrDrop()]
        case Assign(x, e):
            return (compileExp(e) + [WasmInstrVarLocal('set', identToWasmId(x))])
        case IfStmt(cond, thenBody, elseBody):
            instrs = compileExp(cond)
            instrs += [WasmInstrIf(None, compileStmts(thenBody), compileStmts(elseBody))]
            return instrs
        case WhileStmt(cond, body):
            instrs: list[WasmInstr]
            instrs = [
                WasmInstrBlock(
                    identToWasmId(Ident("loop_exit")), 
                    None, 
                    [
                        WasmInstrLoop(identToWasmId(Ident("loop_start")), 
                                      compileExp(cond) + [
                                          WasmInstrIf(
                                              None, 
                                              compileStmts(body) + [WasmInstrBranch(identToWasmId(Ident("loop_start")), False)], [WasmInstrBranch(identToWasmId(Ident("loop_exit")), False)])])
                    ]
                )
            ]
            return instrs

def compileExp(e: exp) -> list[WasmInstr]:
    """
    Compiles the given expression.
    """
    match e:
        #IntConst | Name | Call | UnOp | BinOp
        case IntConst(value):
            return [WasmInstrConst('i64', value)]
        case BoolConst(value):
            return [WasmInstrConst('i32', 1 if value else 0)]
        case Name(name):
            return [WasmInstrVarLocal('get', identToWasmId(name))]
        case Call(name, args):
            instrs: list[WasmInstr] = []
            for arg in args:
                instrs += compileExp(arg)
            match name.name:
                case 'print':
                    match tyOfExp(args[0]):
                        case Int():
                            instrs += [WasmInstrCall(identToWasmId(Ident("print_i64")))]
                        case Bool():
                            instrs += [WasmInstrCall(identToWasmId(Ident("print_bool")))]
                case 'input_int':
                    instrs += [WasmInstrCall(identToWasmId(Ident("input_i64")))]
                case _:
                    instrs += [WasmInstrCall(identToWasmId(name))]
            return instrs
        case UnOp(op, arg):
            match op:
                case USub():
                    return ([WasmInstrConst('i64', 0)] + compileExp(arg) + [WasmInstrNumBinOp('i64', 'sub')])
                case Not():
                    return (compileExp(arg) + [WasmInstrConst('i32', 0)] + [WasmInstrIntRelOp('i32', 'eq')])
        case BinOp(left, op, right):
            instrs = compileExp(left)
            instrs += compileExp(right)
            match op:
                case Add():
                    return compileExp(left) + compileExp(right) + [WasmInstrNumBinOp('i64', 'add')]
                case Sub():
                    return compileExp(left) + compileExp(right) + [WasmInstrNumBinOp('i64', 'sub')]
                case Mul():
                    return compileExp(left) + compileExp(right) + [WasmInstrNumBinOp('i64', 'mul')]
                case Less():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'lt_s')]
                case LessEq():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'le_s')]
                case Eq():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'eq')]
                case Greater():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'gt_s')]
                case GreaterEq():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'ge_s')]
                case NotEq():
                    return compileExp(left) + compileExp(right) + [WasmInstrIntRelOp(tyToLiteral(tyOfExp(left)), 'ne')]
                case And():
                    return compileExp(left) + [WasmInstrIf('i32', compileExp(right), [WasmInstrConst('i32', 0)])]
                case Or():
                    return compileExp(left) + [WasmInstrIf('i32', [WasmInstrConst('i32', 1)], compileExp(right))]




def identToWasmId(ident: ident) -> WasmId:
    return WasmId(f'${ident.name}')

def tyToWasmValType(t: ty) -> WasmValtype:
    match t:
        case Int():
            return 'i64'
        case Bool():
            return 'i32'
        
def tyToLiteral(t: ty) -> Literal['i32', 'i64']:
    match t:
        case Int():
            return 'i64'
        case Bool():
            return 'i32'
        
def tyOfExp(e: exp)-> ty:
    if e.ty is None:
        raise Exception("Expression has no type")
    elif isinstance(e.ty, Void):
        raise Exception("Expression has void type")
    else:
        return e.ty.ty