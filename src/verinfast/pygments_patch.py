from jsx import JsxLexer
from jsx.lexer import TOKENS
from modernmetric.fp import file_process
from pygments.lexers.javascript import TypeScriptLexer
from pygments.lexers._mapping import LEXERS
from pygments.lexers import _lexer_cache


class TypeScriptXLexer(TypeScriptLexer):
    name = 'TypeScriptX'
    aliases = ['tsx', 'typescriptx']
    filenames = ['*.tsx']
    tokens = TOKENS


class Fargs():
    ignore_lexer_errors = False
    dump = False


class Fimporter():
    def items(self):
        return []


# Hack to register an internal lexer.
_lexer_cache['TypeScriptXLexer'] = TypeScriptXLexer
_lexer_cache['JsxLexer'] = JsxLexer

LEXERS['TypeScriptXLexer'] = ('', 'TypeScriptXLexer', ('typescriptx', 'tsx'), ('*.tsx',), ('application/x-typescript', 'text/x-typescript'))
LEXERS['JsxLexers'] = ('', 'JsxLexer', ('react', 'jsx'), ('*.jsx', '*.react'), ('text/jsx'))


fimporter = Fimporter()
fargs = Fargs()
_file = './tests/Blank.tsx'

results = file_process(_file, fargs, fimporter)
print(results)
assert (results[0])


def patch_pygments():
    print('pygments patched')
