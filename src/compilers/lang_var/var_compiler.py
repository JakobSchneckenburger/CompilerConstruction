from lang_var.var_ast import *
from common.wasm import *
import lang_var.var_tychecker as var_tychecker
from common.compilerSupport import *
#import common.utils as utils

def compileModule(m: mod, cfg: CompilerConfig) -> WasmModule:
    """
    Compiles the given module.
    """
    vars = var_tychecker.tycheckModule(m)
    instrs = compileStmts(m.stmts)
    idMain = WasmId('$main')
    locals: list[tuple[WasmId, WasmValtype]] = [(identToWasmId(x), 'i64') for x in vars]
    return WasmModule(imports=wasmImports(cfg.maxMemSize), 
                      exports=[WasmExport("main", WasmExportFunc(idMain))],
                      globals=[],
                      data=[],
                      funcTable=WasmFuncTable([]),
                      funcs=[WasmFunc(idMain, [], None, locals, instrs)])


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

def compileExp(e: exp) -> list[WasmInstr]:
    """
    Compiles the given expression.
    """
    match e:
        #IntConst | Name | Call | UnOp | BinOp
        case IntConst(value):
            return [WasmInstrConst('i64', value)]
        case Name(name):
            return [WasmInstrVarLocal('get', identToWasmId(name))]
        case Call(name, args):
            instrs: list[WasmInstr] = []
            for arg in args:
                instrs += compileExp(arg)
            match name.name:
                case 'print':
                    instrs += [WasmInstrCall(identToWasmId(Ident("print_i64")))]
                case 'input_int':
                    instrs += [WasmInstrCall(identToWasmId(Ident("input_i64")))]
                case _:
                    instrs += [WasmInstrCall(identToWasmId(name))]
            return instrs
        case UnOp(op, arg):
            match op:
                case USub():
                    return ([WasmInstrConst('i64', 0)] + compileExp(arg) + [WasmInstrNumBinOp('i64', 'sub')])
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
    

def identToWasmId(ident: ident) -> WasmId:
    return WasmId(f'${ident.name}')