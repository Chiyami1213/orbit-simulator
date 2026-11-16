"""Figure themes. Categorical series colours are the documented validated palette (fixed order, never cycled);
chrome/ink values follow the same reference. Every mark is direct-labelled, so the sub-3:1 light slots are covered
by the relief rule."""
from __future__ import annotations

SERIES_LIGHT = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
SERIES_DARK = ['#3987e5', '#d95926', '#199e70', '#c98500', '#d55181', '#0ca30c', '#9085e9', '#e66767']

THEMES = {
    'light': dict(surface='#fcfcfb', page='#f9f9f7', ink='#0b0b0b', ink2='#52514e', muted='#898781',
                  grid='#e1e0d9', axis='#c3c2b7', series=SERIES_LIGHT, body='#a9c0ee'),
    'dark': dict(surface='#162039', page='#0f1628', ink='#e8ecf5', ink2='#b4bdd2', muted='#8391ad',
                 grid='#243452', axis='#34466b', series=SERIES_DARK, body='#2c57b8'),
}

# Semantic colour roles -> fixed categorical slot (so colour follows the entity, never its rank)
ROLE_SLOT = {'orbit': 0, 'orbit2': 1, 'orbit3': 2, 'transfer': 2, 'target': 3, 'vel': 6, 'dv': 7, 'vector': 0,
             'accent': 6, 'warn': 7, 'extra': 4, 'good': 5}


def color(theme: str, role: str) -> str:
    t = THEMES[theme]
    if role in ROLE_SLOT:
        return t['series'][ROLE_SLOT[role]]
    if role in t:
        return t[role]
    return role  # already a hex colour
