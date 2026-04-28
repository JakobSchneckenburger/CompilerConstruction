from lark import ParseTree
from lang_var.var_ast import *
from parsers.common import *
import common.log as log

grammarFile = "./src/parsers/lang_var/var_grammar.lark"

def parseModule(args: ParserArgs)-> mod:
    parseTree = parseAsTree(args, grammarFile, 'lvar')
    
    #debug
    print(parseTree.pretty())
    
    ast = parseTreeToModuleAst(parseTree)
    log.debug(f'AST: {ast}')
    return ast


def parseTreeToModuleAst(t: ParseTree)-> mod:
    return Module(parseTreeToStmtListAst(asTree(t.children[0])))

def parseTreeToStmtListAst(t: ParseTree)-> list[stmt]:
    match t.data:
        case 'stmt_list':
            return [parseTreeToStmtAst(asTree(c)) for c in t.children]
        case _:
            raise Exception(f'unhandled parse tree of kind {t.data} for stmt list: {t}')



def parseTreeToStmtAst(t: ParseTree)-> stmt:
    match t.data:
        case 'stmt':
            inner = asTree(t.children[0])

            match inner.data:
                case 'exp_stmt':
                    return StmtExp(parseTreeToExpAst(asTree(inner.children[0])))

                case 'assign_stmt':
                    return Assign(
                        Ident(asToken(inner.children[0]).value),
                        parseTreeToExpAst(asTree(inner.children[1]))
                    )

                case _:
                    raise Exception(f"unknown stmt body: {inner.data}")
        case _:
            raise Exception(f'unhandled parse tree of kind {t.data} for stmt: {t}')


def parseTreeToExpAst(t: ParseTree) -> exp:
    match t.data:
        case 'exp':
            return parseTreeToExpAst(asTree(t.children[0]))

        case 'exp_add':
            l, r = t.children
            return BinOp(
                parseTreeToExpAst(asTree(l)),
                Add(),
                parseTreeToExpAst(asTree(r))
            )

        case 'exp_sub':
            l, r = t.children
            return BinOp(
                parseTreeToExpAst(asTree(l)),
                Sub(),
                parseTreeToExpAst(asTree(r))
            )

        case 'exp_mul':
            l, r = t.children
            return BinOp(
                parseTreeToExpAst(asTree(l)),
                Mul(),
                parseTreeToExpAst(asTree(r))
            )

        case 'exp_1':
            return parseTreeToExpAst(asTree(t.children[0]))

        case  'exp_2':
            return parseTreeToExpAst(asTree(t.children[0]))

        case 'exp_int':
            return IntConst(int(asToken(t.children[0])))

        case 'exp_var':
            return Name(Ident(asToken(t.children[0]).value))

        case 'exp_func_call':
            name = Ident(asToken(t.children[0]).value)
            
            args: list[exp] = []
            for c in t.children[1:]:
                args.append(parseTreeToExpAst(asTree(c)))
            
            return Call(name, args)

        case 'exp_paren':
            return parseTreeToExpAst(asTree(t.children[0]))
        
        case 'exp_usub':
            return UnOp(USub(), parseTreeToExpAst(asTree(t.children[0])))
        
        case _:
            raise Exception(f'unhandled parse tree of kind {t.data} for exp: {t}')
        
#def parseTreeToExpAst(t: ParseTree) -> exp:
#    match t.data:
#        case 'exp_add':
#            e1, e2 = [asTree(c) for c in t.children]
#            return BinOp(parseTreeToExpAst(e1), Add(), parseTreeToExp_1Ast(e2))
#        case 'exp_1':
#            return parseTreeToExp_1Ast(t)
#        case _:
#            raise Exception(f'unhandled parse tree of kind {t.data} for exp: {t}')

#def parseTreeToExp_1Ast(t: ParseTree) -> exp:
#    match t.data:
#        case 'exp_mul':
#            e1, e2 = [asTree(c) for c in t.children]
#            return BinOp(parseTreeToExp_1Ast(e1), Mul(), parseTreeToExp_2Ast(e2))
#        case 'exp_2':
#            return parseTreeToExp_2Ast(asTree(t.children[0]))
#        case _:
#            raise Exception(f'unhandled parse tree of kind {t.data} for exp: {t}')
        

#def parseTreeToExp_2Ast(t: ParseTree) -> exp:
#    match t.data:
#        case 'exp_int':
#            return IntConst(int(asToken(t.children[0])))
#        case 'exp_func_call':
#            name = Ident(asToken(t.children[0]).value)
#            arg = parseTreeToExpAst(asTree(t.children[1]))
#            return Call(name, [arg])
#        case 'exp_var':
#            return Name(asToken(t.children[0]).value)
#        case 'exp_paren':
#            return parseTreeToExpAst(asTree(t.children[0]))
#        case kind:
#            raise Exception(f'unhandled parse tree of kind {kind} for exp: {t}')
