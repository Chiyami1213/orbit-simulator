"""Unicode -> LaTeX conversion for every piece of mathematics the program shows or exports.

``tex(s)`` turns a mixed prose/maths string such as ``"θ* from atan2(ṙ·h/μ, p/r − 1)"`` into
``"$\\theta^{*}$ from $\\mathrm{atan2}(\\dot{r}\\cdot h/\\mu,\\ p/r - 1)$"``: maths runs are wrapped in ``$...$`` (matplotlib mathtext syntax, which is
also valid LaTeX), prose stays outside. Every maths run is checked against matplotlib's parser; a run that cannot be typeset is left as the
original text rather than shown broken.

Celestial-body marks (R⊕, M☉ ...) can be typeset either as the astronomical symbol (``body='symbol'``: R_{\\oplus}) or as a name subscript
(``body='name'``: R_{\\mathrm{earth}}).
"""
from __future__ import annotations
import functools
import re
import unicodedata

GREEK = dict(zip('αβγδεζηθικλμνξοπρστυφχψω', r'\alpha \beta \gamma \delta \varepsilon \zeta \eta \theta \iota \kappa \lambda \mu \nu \xi o \pi \rho \sigma \tau \upsilon \phi \chi \psi \omega'.split()))
GREEK.update(zip('ΓΔΘΛΞΠΣΥΦΨΩ', r'\Gamma \Delta \Theta \Lambda \Xi \Pi \Sigma \Upsilon \Phi \Psi \Omega'.split()))
GREEK['ς'] = r'\sigma'; GREEK['ϕ'] = r'\varphi'; GREEK['ϑ'] = r'\vartheta'
SYMBOLS = {'·': r'\cdot', '×': r'\times', '−': '-', '–': '-', '±': r'\pm', '≈': r'\approx', '≤': r'\leq', '≥': r'\geq', '≠': r'\neq', '→': r'\rightarrow', '⇒': r'\Rightarrow',
           '⇄': r'\rightleftharpoons', '←': r'\leftarrow', '∞': r'\infty', '∈': r'\in', '∂': r'\partial', '∝': r'\propto', '∑': r'\sum', '∫': r'\int',
           '°': r'^{\circ}', '′': "'", '‖': r'\|', '⊥': r'\perp', '∥': r'\parallel', '…': r'\ldots', '↔': r'\leftrightarrow'}
# celestial bodies: symbol (as typeset) and the name used for the subscript style
BODIES = {'⊕': (r'\oplus', 'earth'), '☉': (r'\odot', 'sun'), '☽': ('☽', 'moon'), '☿': ('☿', 'mercury'), '♀': ('♀', 'venus'), '♂': ('♂', 'mars'),
          '♃': ('♃', 'jupiter'), '♄': ('♄', 'saturn'), '♅': ('♅', 'uranus'), '♆': ('♆', 'neptune'), '♇': ('♇', 'pluto')}
SUB = dict(zip('₀₁₂₃₄₅₆₇₈₉₊₋₌ₐₑₒₓₕₖₗₘₙₚₛₜ', '0123456789+-=aeoxhklmnpst'))
SUP = dict(zip('⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼ⁿⁱ', '0123456789+-=ni'))
FUNCS = {'sin', 'cos', 'tan', 'sinh', 'cosh', 'tanh', 'arcsin', 'arccos', 'arctan', 'log', 'exp', 'min', 'max', 'ln'}
ACCENT = {'\u0304': 'bar', '\u0305': 'bar', '\u0302': 'hat', '\u0307': 'dot', '\u0308': 'ddot', '\u0303': 'tilde', '\u0301': 'acute', '\u0300': 'grave'}
MATHCH = set(GREEK) | set(SYMBOLS) | set(SUB) | set(SUP) | set(ACCENT) | set(BODIES) | set('√')
OPERATORS = {'=', '+', '-', '−', '×', '·', '/', '<', '>', '≈', '≤', '≥', '≠', '→', '⇒', '⇄', '±', '∈', '∝', '|'}
BODY_CH = ''.join(BODIES)


def _accent(base: str, marks: str) -> str:
    out = GREEK.get(base, base)
    for mk in marks:
        name = ACCENT.get(mk)
        if name: out = '\\' + name + '{' + out + '}'
    return out


def _decompose(tok: str) -> str:
    """NFD-decompose so 'ê', 'ĥ', 'ṙ', 'v̄' are base + combining mark, then turn those into \\hat{e}, \\dot{r}, \\bar{v} ..."""
    return re.sub(r'(.)((?:[\u0300-\u036f])+)', lambda m: _accent(m.group(1), m.group(2)), unicodedata.normalize('NFD', tok))


def _sqrt(s: str) -> str:
    """'√(μ/a³)' -> '\\sqrt{μ/a³}': take a balanced parenthesised argument or the following token."""
    while '√' in s:
        i = s.index('√'); rest = s[i + 1:]
        if rest.startswith('('):
            depth = 0
            for j, ch in enumerate(rest):
                depth += (ch == '(') - (ch == ')')
                if depth == 0: arg, tail = rest[1:j], rest[j + 1:]; break
            else: arg, tail = rest[1:], ''
        else:
            m = re.match(r'[A-Za-z0-9α-ωΑ-Ω_^{}\\.]+', rest); arg = m.group(0) if m else ''; tail = rest[len(arg):]
        s = s[:i] + r'\sqrt{' + arg + '}' + tail
    return s


def _piece(tok: str, body: str) -> str:
    """One space-free maths piece -> LaTeX/mathtext."""
    def bodymark(m):
        sym, name = BODIES[m.group(2)]; mark = sym if body == 'symbol' else r'\mathrm{' + name + '}'
        return (m.group(1) + '_{' + mark + '}') if m.group(1) else (mark if body == 'symbol' else r'\mathrm{' + name + '}')
    t = re.sub('([A-Za-z\u0370-\u03ff]?)([' + BODY_CH + '])', bodymark, tok)
    t = _decompose(t)
    t = re.sub('[' + ''.join(SUB) + ']+', lambda m: '_{' + ''.join(SUB[c] for c in m.group(0)) + '}', t)
    t = re.sub('[' + ''.join(SUP) + ']+', lambda m: '^{' + ''.join(SUP[c] for c in m.group(0)) + '}', t)
    t = _sqrt(t)
    t = ''.join(((GREEK[c] + ' ') if c in GREEK else (SYMBOLS[c] + ' ') if c in SYMBOLS else c) for c in t)
    t = re.sub(r'(?<=[A-Za-z}\\ ])\*', '^{*}', t) if '*' in t else t                        # θ* -> \theta^{*}
    t = re.sub(r'_([A-Za-z0-9]+)', lambda m: '_{' + (r'\mathrm{' + m.group(1) + '}' if len(m.group(1)) > 1 and m.group(1).isalpha() else m.group(1)) + '}', t)
    t = t.replace('%', r'\%').replace('&', r'\&').replace('#', r'\#')

    def word(m):                                                                                # multi-letter ASCII words: functions or upright text
        w = m.group(0)
        return '\\' + w + ' ' if w in FUNCS else r'\mathrm{' + w + '}'
    t = re.sub(r'(?<![\\A-Za-z{])[A-Za-z][A-Za-z0-9]+(?![A-Za-z{}])', word, t)
    return re.sub(r' +', ' ', t).strip()


def _math(unit: str, body: str) -> str:
    return ' '.join(_piece(p, body) for p in unit.split(' ') if p)


@functools.lru_cache(maxsize=4096)
def valid(math: str) -> bool:
    try:
        from matplotlib.mathtext import MathTextParser
        MathTextParser('path').parse('$' + math + '$'); return True
    except Exception:
        return False


def _units(toks: list[str]) -> list[str]:
    """Merge space-separated tokens so a parenthesised group stays in one unit, e.g. 'atan2(ṙ·h/μ, p/r − 1)'."""
    out, cur, depth = [], '', 0
    for t in toks:
        cur = t if not cur else cur + ' ' + t
        depth += t.count('(') + t.count('[') - t.count(')') - t.count(']')
        if depth <= 0: out.append(cur); cur, depth = '', 0
    if cur: out.append(cur)
    return out


def _core(tok: str):
    m = re.match(r'^(.*?)([.,;:?!]*)$', tok); return m.group(1), m.group(2)


def _is_prose_group(core: str) -> bool:
    """A parenthesised group that contains an ordinary word ("(0 = skip; circular only)") is prose, not a formula."""
    return bool(re.search(r'(?<![A-Za-z\\])(?!(?:' + '|'.join(FUNCS) + r')\b)[a-z]{3,}(?![A-Za-z0-9{])', core)) and core.startswith(('(', '['))


def _strong(core: str) -> bool:
    return (any(c in MATHCH for c in core) or bool(re.search(r'[_^=<>]', core)) or core in OPERATORS) and not _is_prose_group(core)


@functools.lru_cache(maxsize=16384)
def tex(s: str, body: str = 'symbol') -> str:
    """Mixed prose + maths -> prose with each maths run wrapped in $...$ (LaTeX / mathtext)."""
    s = re.sub('[\u2009\u200a\u202f\u00a0\u2002\u2003]', ' ', s)                   # thin / non-breaking spaces have no glyph in the maths fonts
    if not s or not (any(c in MATHCH for c in s) or re.search(r'[_^=<>]', s)):
        return s
    units = _units(s.split(' ')); cores = [_core(u) for u in units]; mark = [bool(c[0]) and _strong(c[0]) for c in cores]
    for _ in range(2):                                          # lone letters / numbers touching maths are variables / coefficients
        for i, (c, _p) in enumerate(cores):
            if mark[i] or not c or not re.fullmatch(r'[A-Za-z]|\d+(?:\.\d+)?', c): continue
            if (i > 0 and mark[i - 1]) or (i + 1 < len(units) and mark[i + 1]): mark[i] = True
    out, run = [], []

    def flush():
        if run:
            m = _math(' '.join(run), body); out.append('$' + m + '$' if valid(m) else ' '.join(run)); run.clear()
    for i, u in enumerate(units):
        c, punct = cores[i]
        if mark[i] and c:
            run.append(c)
            if punct: flush(); out[-1] += punct
        else:
            flush(); out.append(u)
    flush()
    return ' '.join(out)


def plain(s: str) -> str:
    """Strip the $ delimiters (for places that cannot typeset maths)."""
    return s.replace('$', '')


def prose_escape_latex(s: str) -> str:
    """Escape characters LaTeX text mode treats specially (MATLAB's latex interpreter, outside $...$)."""
    special = {'~': r'\textasciitilde{}', '^': r'\^{}', '\\': r'\textbackslash{}'}
    return re.sub(r'([%&#_{}~^\\])', lambda m: special.get(m.group(1), '\\' + m.group(1)), s)
