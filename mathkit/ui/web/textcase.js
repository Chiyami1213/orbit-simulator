/* Text-case helpers.
   apa(s) : APA title case for headers and labels (capitalize the first and last word, every word of 4+ letters and every major word;
            keep articles, short conjunctions and short prepositions lower case; capitalize the word after a colon or dash;
            leave anything inside parentheses, symbols, numbers and single letters untouched).
   lc(s)  : lower case for explanatory text. Only ordinary Capitalized English words are lowered, so symbols such as Ω, Δv, V_D, TOF,
            HW4 or R_body are never altered (Ω and ω are different angles!). */
(function (root) {
  const MINOR = new Set(['a', 'an', 'the', 'and', 'as', 'at', 'but', 'by', 'for', 'if', 'in', 'nor', 'of', 'off', 'on', 'or', 'per', 'so', 'to', 'up', 'via', 'vs', 'vs.', 'yet']);
  const PLAIN = /^([“"]*)([a-z]+(?:-[a-z]+)*)([.,:;?!”"]*)$/;
  const cap = p => p ? p[0].toUpperCase() + p.slice(1) : p;

  function apa(str) {
    const toks = String(str).split(' '); let depth = 0, brk = true; const info = [];
    const out = toks.map((t, i) => {
      const inside = depth > 0 || t.startsWith('(');
      depth = Math.max(0, depth + (t.match(/\(/g) || []).length - (t.match(/\)/g) || []).length);
      const m = inside ? null : PLAIN.exec(t); let res = t;
      if (m) {
        const hy = m[2].includes('-');
        const parts = m[2].split('-').map((p, j) => ((p.length > 1 || (hy && j === 0 && brk)) && ((j === 0 && brk) || p.length >= 4 || !MINOR.has(p))) ? cap(p) : p);
        res = m[1] + parts.join('-') + m[3]; info[i] = true;
      }
      if (!inside && (/[:]$/.test(t) || ['—', '–', '·'].includes(t))) brk = true; else if (t !== '') brk = false;
      return res;
    });
    for (let i = out.length - 1; i >= 0; i--) {                       // the last word is always capitalized
      if (info[i]) { out[i] = out[i].replace(/^([“"]*)([a-z]+)((?:-[a-z]+)*)(?=[.,:;?!”"]*$)/, (_, a, b, c) => a + b + c.replace(/-([a-z]+)$/, (x, w) => c ? '-' + cap(w) : x)); if (!/-/.test(out[i])) out[i] = out[i].replace(/^([“"]*)([a-z]{2,})/, (_, a, b) => a + cap(b)); break; }
      if (out[i] && /[A-Za-z]/.test(out[i])) break;
    }
    return out.join(' ');
  }
  const lc = str => String(str).replace(/\b[A-Z][a-z]+\b/g, w => w.toLowerCase());
  const api = { apa, lc };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else Object.assign(root, api);
})(typeof window !== 'undefined' ? window : globalThis);
