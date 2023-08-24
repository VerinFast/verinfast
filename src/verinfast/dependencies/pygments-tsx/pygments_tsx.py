from pygments.lexers.javascript import TypeScriptLexer


class CustomLexer(TypeScriptLexer):
    name = 'TypeScriptX'
    aliases = ['tsx', 'typescriptx']
    filenames = ['*.tsx']
