"""Central HTML-escape wrapper. Every dynamic string in Telegram output goes through this.

Per UNIVERSAL_DISCIPLINE §III, unescaped operator-controlled or computed strings in markup
have been the single most-shipped bug class. Do not bypass.
"""
from __future__ import annotations

from html import escape


def esc(value: object) -> str:
    """Escape any value for insertion into Telegram HTML.

    None -> empty string. All other types coerced via str() before escaping.
    quote=True escapes both single and double quotes.
    """
    if value is None:
        return ""
    return escape(str(value), quote=True)
