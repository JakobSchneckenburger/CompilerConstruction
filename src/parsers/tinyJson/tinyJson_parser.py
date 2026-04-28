from parsers.common import *

type Json = str | int | dict[str, Json]

def ruleJson(toks: TokenStream) -> Json:
    return alternatives("json", toks, [ruleObject, ruleString, ruleInt])

def ruleObject(toks: TokenStream) -> dict[str, Json]:
    toks.ensureNext("LBRACE")
    entries = ruleEntryList(toks)
    toks.ensureNext("RBRACE")
    return entries

def ruleEntryList(toks: TokenStream) -> dict[str, Json]:
    if toks.lookahead().type == "STRING":
        return ruleEntryListNotEmpty(toks)
    else:
        return {}

def ruleEntryListNotEmpty(toks: TokenStream) -> dict[str, Json]:
    entry = ruleEntry(toks)
    if toks.lookahead().type == "COMMA":
        toks.ensureNext("COMMA")
        rest = ruleEntryListNotEmpty(toks)
        return {entry[0]: entry[1], **rest}
    else:
        return {entry[0]: entry[1]}

def ruleEntry(toks: TokenStream) -> tuple[str, Json]:
    key = toks.ensureNext("STRING").value[1:-1]

    toks.ensureNext("COLON")
    value = ruleJson(toks)
    return (key, value)

def ruleString(toks: TokenStream) -> str:
    return toks.ensureNext("STRING").value[1:-1]

def ruleInt(toks: TokenStream) -> int:
    return int(toks.ensureNext("INT").value)

def parse(code: str) -> Json:
    parser = mkLexer("./src/parsers/tinyJson/tinyJson_grammar.lark")
    tokens = list(parser.lex(code))
    log.info(f'Tokens: {tokens}')
    toks = TokenStream(tokens)
    res = ruleJson(toks)
    toks.ensureEof(code)
    return res