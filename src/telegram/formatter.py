"""Style A Telegram card formatter — redesigned per Aug 2026 walkthrough.

All dynamic fields routed through _esc() per UNIVERSAL_DISCIPLINE §III.
Static labels ("LEVELS", "Stop:", etc.) are author-controlled and safe as-is.

Card structure (final spec):
  [SHADOW banner — only if mode=SHADOW]
  header row  — medal · DIR · pos · slip
  symbol line — SYMBOL (addr…) · rank
  edge line   — E1.v1 · name (chain)
  [PRIOR block — hidden when no prior]
  LEVELS      — momentum · price · stop · TP1 · expires
  ONCHAIN VITALS — gate checks w/ inline story deltas
  CONTEXT     — flow deltas
  WHY         — thesis + one evidence bullet
  FOOTER      — SIGNAL_ID + chart link

Kill switches: none at formatter level — formatting is pure. Callers
gate emission via SIGNAL_EMISSION_DISABLED / EMISSION_DISABLED.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from src.edges.base import Signal
from src.telegram._esc import esc


# ---------- data-transport dataclasses ------------------------------------


@dataclass
class PriorCall:
    """Populated by caller from resolutions.jsonl when a prior call exists."""

    edge_code: str
    outcome: str  # 'TP1' | 'SL' | 'EXPIRED' | 'INVALID'
    days_ago: int


@dataclass
class HistoryDiff:
    """Populated by caller from snapshot-history diff layer (task 9).
    Every field optional — cells render blank when unavailable."""

    liq_pct_12h: Optional[float] = None       # 0.42 -> "+42% in 12h"
    vol_ratio_yesterday: Optional[float] = None  # 3.2 -> "3.2× yesterday"
    holders_delta_24h: Optional[int] = None   # 180 -> "+180 in 24h"
    top10_direction: Optional[str] = None     # "tightening" | "widening" | "stable"


@dataclass
class Resolution:
    """Payload for a resolution reply (TP1/SL/EXPIRED/INVALID)."""

    signal_id: str
    symbol: str
    outcome: str
    r_multiple: Optional[float]
    held_minutes: float
    exit_price: Optional[float]


# ---------- constants -----------------------------------------------------

_MEDAL_MAX = 5
_PROGRESS_TARGET = 30
_PROGRESS_BAR_WIDTH = 10

_CHAIN_SHORT = {
    "solana": "SOL",
    "ethereum": "ETH",
    "bsc": "BSC",
    "base": "BASE",
    "arbitrum": "ARB",
}

_DIR_EMOJI = {
    "long": "🟢",
    "short_advisory": "🟠",
    "short_perp": "🔴",
}

_DIR_WORD = {
    "long": "LONG",
    "short_advisory": "CLOSE-LONG",
    "short_perp": "SHORT",
}

_DEX_CHAIN_PATH = {
    "solana": "solana",
    "ethereum": "ethereum",
    "bsc": "bsc",
    "base": "base",
    "arbitrum": "arbitrum",
}


# ---------- pure formatting helpers ---------------------------------------


def _milestone(n: int) -> str:
    if n <= 0:
        return "day zero"
    if n <= 9:
        return "gathering data"
    if n <= 19:
        return "past midpoint"
    if n <= 29:
        return "final stretch"
    return "decision ready"


def _progress_bar(n: int, target: int = _PROGRESS_TARGET, width: int = _PROGRESS_BAR_WIDTH) -> str:
    if target <= 0:
        frac = 0.0
    else:
        frac = min(1.0, max(0.0, n / target))
    filled = int(round(frac * width))
    return "█" * filled + "░" * (width - filled)


def compute_medal(state) -> int:  # noqa: ANN001
    """Medal formula (locked in card walkthrough):
      start 3
      +1 if top10 < 25%
      +1 if vol/liq > 5x
      -1 if holders < 300
      -1 if age < 12h
      clamp [1,5]
    """
    medal = 3
    if state.top10_pct is not None and state.top10_pct < 0.25:
        medal += 1
    if state.liq_usd and state.vol_24h_usd:
        if (state.vol_24h_usd / state.liq_usd) > 5:
            medal += 1
    if state.holder_count is not None and state.holder_count < 300:
        medal -= 1
    if state.age_hours is not None and state.age_hours < 12:
        medal -= 1
    return max(1, min(_MEDAL_MAX, medal))


def slip_bps_round_trip(pos_usd: float, liq_usd: Optional[float]) -> int:
    """CPMM rough estimate — one-way ≈ pos / (liq/2); round-trip = 2× one-way.

    Returns integer bps. Sentinel 9999 for missing/zero liquidity.
    """
    if not liq_usd or liq_usd <= 0:
        return 9999
    one_way_bps = pos_usd * 20000.0 / liq_usd
    return int(round(2 * one_way_bps))


def _short_addr(addr: str) -> str:
    if not addr or len(addr) < 12:
        return addr or ""
    return f"{addr[:4]}…{addr[-4:]}"


def _fmt_price(x: Optional[float]) -> str:
    if x is None:
        return "—"
    if x >= 100:
        return f"${x:,.2f}"
    if x >= 1:
        return f"${x:.4f}"
    if x >= 0.01:
        return f"${x:.5f}"
    if x >= 0.0001:
        return f"${x:.6f}"
    return f"${x:.4e}"


def _fmt_pct_from_decimal(x: Optional[float], decimals: int = 1) -> str:
    if x is None:
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x * 100:.{decimals}f}%"


def _fmt_pct_from_percent(x: Optional[float], decimals: int = 1) -> str:
    """DexScreener returns priceChange as percent already (12.0 = +12%)."""
    if x is None:
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.{decimals}f}%"


def _fmt_int(n: Optional[int]) -> str:
    if n is None:
        return "—"
    return f"{n:,}"


def _fmt_usd_compact(x: Optional[float]) -> str:
    if x is None:
        return "—"
    ax = abs(x)
    if ax >= 1e9:
        return f"${x / 1e9:.1f}B"
    if ax >= 1e6:
        return f"${x / 1e6:.1f}M"
    if ax >= 1e3:
        return f"${x / 1e3:.0f}k"
    return f"${x:.0f}"


def _chain_short(chain: str) -> str:
    return _CHAIN_SHORT.get(chain.lower(), chain.upper()[:5])


def signal_id(edge_code: str, chain: str, emitted_at: datetime, symbol: str) -> str:
    """Canonical signal id: E1-SOL-20260803T142211Z-tolywifhat."""
    if emitted_at.tzinfo is None:
        emitted_at = emitted_at.replace(tzinfo=timezone.utc)
    ts = emitted_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sym_clean = re.sub(r"[^A-Za-z0-9]", "", symbol or "")[:24].lower()
    return f"{edge_code}-{_chain_short(chain)}-{ts}-{sym_clean}"


# ---------- block builders ------------------------------------------------


def _shadow_banner(mode: str, resolved: int, target: int = _PROGRESS_TARGET) -> str:
    if mode.upper() != "SHADOW":
        return ""
    bar = _progress_bar(resolved, target)
    return (
        "🔇 SHADOW · observe only\n"
        f"[{esc(bar)}] {esc(resolved)}/{esc(target)} tracked · {esc(_milestone(resolved))}\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    )


def _header(
    medal: int,
    direction: str,
    pos_usd: float,
    slip_bps: int,
    symbol: str,
    addr: str,
    rank: Optional[int],
) -> str:
    stars = "⭐" * medal
    dir_emoji = _DIR_EMOJI.get(direction.lower(), "⚪")
    dir_word = _DIR_WORD.get(direction.lower(), direction.upper())
    rank_str = f"#{_fmt_int(rank)}" if rank is not None else "#—"
    line1 = f"{esc(stars)}  {dir_emoji} {esc(dir_word)} · ${esc(int(pos_usd))} · ~{esc(slip_bps)}bps slip"
    line2 = f"{esc((symbol or '').upper())} ({esc(_short_addr(addr))})  {esc(rank_str)}"
    return line1 + "\n" + line2 + "\n"


def _edge_line(edge_code: str, edge_version: int, edge_name: str, chain: str) -> str:
    return f"🎯 {esc(edge_code)}.v{esc(edge_version)} · {esc(edge_name)} ({esc(chain)})\n"


def _prior_block(prior: Optional[PriorCall]) -> str:
    if prior is None:
        return ""
    return (
        "\n"
        f"📎 PRIOR: {esc(prior.edge_code)} {esc(prior.outcome)} {esc(prior.days_ago)}d ago\n"
        "This token was called before — this is how the last call ended.\n"
    )


def _levels_block(signal: Signal, state, emitted_at: datetime) -> str:  # noqa: ANN001
    ph1 = state.price_change_h1
    ph24 = state.price_change_h24
    thesis_hours = signal.thesis_window_min // 60
    expires_at = emitted_at + timedelta(minutes=signal.thesis_window_min)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    exp_utc = expires_at.astimezone(timezone.utc)
    # Avoid platform-specific %-d / %#d — use .day int directly.
    expires_str = f"{exp_utc.strftime('%b')} {exp_utc.day}, {exp_utc.strftime('%H:%M')}Z"

    entry = signal.entry_price
    stop_pct = (signal.stop_price - entry) / entry if entry else 0.0
    tp1_pct = (signal.tp1_price - entry) / entry if entry else 0.0

    lines = [
        "LEVELS",
        f"📈 {esc(_fmt_pct_from_percent(ph1))} 1h · {esc(_fmt_pct_from_percent(ph24))} 24h",
        f"💵 Price:  <b>{esc(_fmt_price(entry))}</b>  · fill in {esc(signal.entry_window_min)} min",
        f"🔴 Stop:   <b>{esc(_fmt_price(signal.stop_price))}</b>  · {esc(_fmt_pct_from_decimal(stop_pct))}",
        f"🟢 TP1:    <b>{esc(_fmt_price(signal.tp1_price))}</b>  · {esc(_fmt_pct_from_decimal(tp1_pct))}",
        f"⏳ Expires in {esc(thesis_hours)}h · {esc(expires_str)}",
    ]
    return "\n".join(lines) + "\n"


def _vitals_row(icon: str, label: str, value: str, story: str, gate: str) -> str:
    """Single vitals line — label left, value + optional story mid, gate right."""
    story_part = f" · {esc(story)}" if story else ""
    return f"{icon} {label:<12} {esc(value)}{story_part}    ({esc(gate)})"


def _onchain_block(state, history: Optional[HistoryDiff], pos_usd: float) -> str:  # noqa: ANN001
    liq_val = _fmt_usd_compact(state.liq_usd) if state.liq_usd else "—"
    turnover = (state.vol_24h_usd / state.liq_usd) if (state.liq_usd and state.vol_24h_usd) else None
    turnover_val = f"{turnover:.1f}×/24h" if turnover is not None else "—"
    holders_val = _fmt_int(state.holder_count) if state.holder_count is not None else "—"
    top10_val = f"{state.top10_pct * 100:.1f}%" if state.top10_pct is not None else "—"
    age_val = f"{state.age_hours / 24:.1f}d" if state.age_hours is not None else "—"
    slip_val = f"~{slip_bps_round_trip(pos_usd, state.liq_usd)}bps"

    # story cells — blank when history not yet built
    liq_story = ""
    turn_story = ""
    hold_story = ""
    top10_story = ""
    if history is not None:
        if history.liq_pct_12h is not None:
            liq_story = _fmt_pct_from_decimal(history.liq_pct_12h) + " in 12h"
        if history.vol_ratio_yesterday is not None:
            turn_story = f"{history.vol_ratio_yesterday:.1f}× yesterday"
        if history.holders_delta_24h is not None:
            sign = "+" if history.holders_delta_24h > 0 else ""
            hold_story = f"{sign}{history.holders_delta_24h:,} in 24h"
        if history.top10_direction:
            top10_story = history.top10_direction

    lines = [
        "",
        "ONCHAIN VITALS",
        _vitals_row("✅", "Liquidity", liq_val, liq_story, "min $100k"),
        _vitals_row("✅", "Turnover", turnover_val, turn_story, "min 1×"),
        _vitals_row("✅", "Holders", holders_val, hold_story, "min 100"),
        _vitals_row("✅", "Top-10", top10_val, top10_story, "max 40% for E1"),
        _vitals_row("✅", "Age", age_val, "", "window 6h–30d"),
        f"🎯 {'Your slip':<12} {esc(slip_val)}    (${esc(int(pos_usd))} exit, round-trip)",
    ]
    return "\n".join(lines) + "\n"


def _context_block(state) -> str:  # noqa: ANN001
    lines = ["", "📖 CONTEXT"]
    if state.buys_h24 is not None and state.sells_h24 is not None:
        total = state.buys_h24 + state.sells_h24
        if total > 0:
            buy_pct = state.buys_h24 / total * 100
            direction = "accumulation, not distribution" if buy_pct >= 55 else \
                "distribution, not accumulation" if buy_pct <= 45 else "balanced flow"
            lines.append(
                f"📈 Buyers led {esc(f'{buy_pct:.0f}%')} "
                f"({esc(_fmt_int(state.buys_h24))} / {esc(_fmt_int(state.sells_h24))}) — {esc(direction)}"
            )
    if state.price_change_h1 is not None and state.price_change_h24 is not None:
        h1, h24 = state.price_change_h1, state.price_change_h24
        # "pace holding" if 1h has same sign as 24h and its hourly rate exceeds 24h's average
        h24_hourly_rate = h24 / 24.0
        if h1 * h24 >= 0 and abs(h1) >= abs(h24_hourly_rate):
            pace = "pace holding, not fading"
        elif h1 * h24 < 0:
            pace = "reversing"
        else:
            pace = "fading"
        lines.append(
            f"🎯 1h {esc(_fmt_pct_from_percent(h1))} vs 24h {esc(_fmt_pct_from_percent(h24))} — {esc(pace)}"
        )
    if len(lines) == 2:  # nothing added
        return ""
    return "\n".join(lines) + "\n"


def _why_block(signal: Signal) -> str:
    narrative = signal.thesis_narrative or "(no thesis narrative)"
    evidence = signal.thesis_evidence or ""
    lines = ["", "WHY THIS SETUP", esc(narrative)]
    if evidence:
        lines.append(f"🎯 {esc(evidence)}")
    return "\n".join(lines) + "\n"


def _footer(sid: str, chain: str, pair_addr: str) -> str:
    dex_chain = _DEX_CHAIN_PATH.get(chain.lower(), chain.lower())
    chart_url = f"https://dexscreener.com/{dex_chain}/{pair_addr}"
    return (
        "\n"
        f"📎 ID: {esc(sid)}\n"
        f'   📊 <a href="{esc(chart_url)}">Chart → {esc(dex_chain)}/{esc(_short_addr(pair_addr))}</a>\n'
    )


# ---------- public API ----------------------------------------------------


def render_card(
    *,
    signal: Signal,
    state,  # noqa: ANN001 — TokenState from snapshotter
    mode: str,
    emitted_at: datetime,
    edge_version: int = 1,
    edge_short_name: str = "",
    resolved_count: int = 0,
    resolution_target: int = _PROGRESS_TARGET,
    position_usd: float = 15.0,
    cg_rank: Optional[int] = None,
    prior: Optional[PriorCall] = None,
    history: Optional[HistoryDiff] = None,
) -> str:
    """Assemble the full Style A card. Returns Telegram HTML."""
    medal = compute_medal(state)
    slip = slip_bps_round_trip(position_usd, state.liq_usd)
    pair_addr = (signal.card_extras or {}).get("pair_addr", "")
    sid = signal_id(signal.edge_code, signal.chain, emitted_at, signal.symbol)

    parts = [
        _shadow_banner(mode, resolved_count, resolution_target),
        _header(medal, signal.direction, position_usd, slip, signal.symbol, signal.token_addr, cg_rank),
        _edge_line(signal.edge_code, edge_version, edge_short_name, signal.chain),
        _prior_block(prior),
        "\n" + _levels_block(signal, state, emitted_at),
        _onchain_block(state, history, position_usd),
        _context_block(state),
        _why_block(signal),
        _footer(sid, signal.chain, pair_addr),
    ]
    return "".join(parts)


def render_resolution(res: Resolution) -> str:
    """Format the reply-message that lands under the original card on resolution."""
    icon = {"TP1": "✅", "SL": "❌", "EXPIRED": "⌛", "INVALID": "🚫"}.get(res.outcome, "❔")
    r_str = f"{res.r_multiple:+.2f}R" if res.r_multiple is not None else "n/a"
    line1 = f"{icon} {esc(res.outcome)}  {esc((res.symbol or '').upper())}   {esc(r_str)}   in {esc(int(res.held_minutes))}m"
    line2 = f" → SIGNAL_ID: {esc(res.signal_id)}"
    return line1 + "\n" + line2 + "\n"
