"""Signal review — reads shadow_log + resolutions, produces a report.

Replaces Telegram during SHADOW-only phase. Lets the operator eyeball
recent calls against outcomes to spot bad ones fast.

No I/O in the compute functions — CLI wrapper handles reading/printing.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Optional


@dataclass
class Row:
    """One signal, matched to its resolution if any."""

    signal_id: str
    edge_code: str
    edge_version: int
    chain: str
    symbol: str
    token_addr: str
    emitted_at: datetime
    entry_price: float
    stop_price: float
    tp1_price: float
    # resolution fields (None if still open)
    resolved_at: Optional[datetime] = None
    outcome: Optional[str] = None  # 'TP1' | 'SL' | 'EXPIRED' | 'INVALID'
    r_multiple: Optional[float] = None
    exit_price: Optional[float] = None
    held_minutes: Optional[float] = None


@dataclass
class EdgeStats:
    edge_code: str
    n_total: int = 0
    n_resolved: int = 0        # TP1 + SL + EXPIRED (excludes INVALID)
    n_tp1: int = 0
    n_sl: int = 0
    n_expired: int = 0
    n_invalid: int = 0
    n_open: int = 0
    win_rate: Optional[float] = None
    median_r: Optional[float] = None
    total_r: Optional[float] = None


@dataclass
class Report:
    generated_at: datetime
    window_days: int
    rows: list[Row]
    per_edge: dict[str, EdgeStats] = field(default_factory=dict)
    open_rows: list[Row] = field(default_factory=list)


def _chain_short(chain: str) -> str:
    return {"solana": "SOL", "ethereum": "ETH", "bsc": "BSC", "base": "BASE"}.get(
        chain.lower(), chain.upper()[:5]
    )


def _reconstruct_signal_id(edge_code: str, chain: str, emitted_at: datetime, symbol: str) -> str:
    """Mirror src/telegram/formatter.signal_id — we don't import to keep this
    module free of the formatter dependency."""
    import re

    if emitted_at.tzinfo is None:
        emitted_at = emitted_at.replace(tzinfo=timezone.utc)
    ts = emitted_at.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    sym_clean = re.sub(r"[^A-Za-z0-9]", "", symbol or "")[:24].lower()
    return f"{edge_code}-{_chain_short(chain)}-{ts}-{sym_clean}"


def _iter_jsonl(path: Path) -> Iterable[dict]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def _load_resolutions(path: Path) -> dict[tuple[str, str, str], dict]:
    """Key: (edge_code, token_addr, emitted_ts_utc) — same as resolver."""
    out: dict[tuple[str, str, str], dict] = {}
    for row in _iter_jsonl(path):
        try:
            key = (row["edge_code"], row["token_addr"], row["emitted_ts_utc"])
            out[key] = row
        except KeyError:
            continue
    return out


def build_report(
    shadow_path: Path,
    resolutions_path: Path,
    window_days: int = 30,
    now: Optional[datetime] = None,
) -> Report:
    """Join shadow_log rows with resolutions rows; compute per-edge stats."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=window_days)
    resolutions = _load_resolutions(resolutions_path)

    rows: list[Row] = []
    for raw in _iter_jsonl(shadow_path):
        try:
            emitted_at = datetime.fromisoformat(raw["emitted_ts_utc"])
        except (KeyError, ValueError):
            continue
        if emitted_at < cutoff:
            continue

        sig = raw.get("signal") or {}
        edge_code = raw.get("edge_code") or sig.get("edge_code") or ""
        edge_version = raw.get("edge_version", 1)
        chain = sig.get("chain") or raw.get("chain") or ""
        token_addr = sig.get("token_addr") or ""
        symbol = sig.get("symbol") or ""

        row = Row(
            signal_id=_reconstruct_signal_id(edge_code, chain, emitted_at, symbol),
            edge_code=edge_code,
            edge_version=edge_version,
            chain=chain,
            symbol=symbol,
            token_addr=token_addr,
            emitted_at=emitted_at,
            entry_price=float(sig.get("entry_price") or 0.0),
            stop_price=float(sig.get("stop_price") or 0.0),
            tp1_price=float(sig.get("tp1_price") or 0.0),
        )

        res = resolutions.get((edge_code, token_addr, raw["emitted_ts_utc"]))
        if res:
            try:
                row.resolved_at = datetime.fromisoformat(res["resolved_ts_utc"])
            except (KeyError, ValueError):
                pass
            row.outcome = res.get("outcome")
            row.r_multiple = res.get("r_multiple")
            row.exit_price = res.get("exit_price")
            row.held_minutes = res.get("held_minutes")

        rows.append(row)

    return _summarize(rows, now, window_days)


def _summarize(rows: list[Row], now: datetime, window_days: int) -> Report:
    per_edge: dict[str, EdgeStats] = {}
    for r in rows:
        stats = per_edge.setdefault(r.edge_code, EdgeStats(edge_code=r.edge_code))
        stats.n_total += 1
        if r.outcome is None:
            stats.n_open += 1
        elif r.outcome == "TP1":
            stats.n_tp1 += 1
        elif r.outcome == "SL":
            stats.n_sl += 1
        elif r.outcome == "EXPIRED":
            stats.n_expired += 1
        elif r.outcome == "INVALID":
            stats.n_invalid += 1

    for stats in per_edge.values():
        stats.n_resolved = stats.n_tp1 + stats.n_sl + stats.n_expired
        edge_rows = [r for r in rows if r.edge_code == stats.edge_code]
        r_multiples = [r.r_multiple for r in edge_rows
                       if r.outcome in ("TP1", "SL", "EXPIRED") and r.r_multiple is not None]
        if r_multiples:
            stats.median_r = statistics.median(r_multiples)
            stats.total_r = sum(r_multiples)
        if stats.n_resolved > 0:
            stats.win_rate = stats.n_tp1 / stats.n_resolved

    open_rows = [r for r in rows if r.outcome is None]
    return Report(
        generated_at=now,
        window_days=window_days,
        rows=rows,
        per_edge=per_edge,
        open_rows=open_rows,
    )


# ---------- render: console --------------------------------------------


def render_console(report: Report) -> str:
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append(f"CodeOracle signal review — last {report.window_days} days")
    lines.append(f"generated: {report.generated_at.isoformat(timespec='seconds')}")
    lines.append(f"total signals in window: {len(report.rows)}   open: {len(report.open_rows)}")
    lines.append("=" * 70)

    lines.append("\nPER-EDGE STATS")
    lines.append("-" * 70)
    if not report.per_edge:
        lines.append("  (no signals yet)")
    for code in sorted(report.per_edge):
        s = report.per_edge[code]
        win = f"{s.win_rate * 100:.0f}%" if s.win_rate is not None else "—"
        med = f"{s.median_r:+.2f}R" if s.median_r is not None else "—"
        tot = f"{s.total_r:+.2f}R" if s.total_r is not None else "—"
        lines.append(
            f"  {code}: total={s.n_total}  resolved={s.n_resolved}  open={s.n_open}  "
            f"invalid={s.n_invalid}  |  TP1/SL/EXPIRED={s.n_tp1}/{s.n_sl}/{s.n_expired}"
        )
        lines.append(f"       win rate: {win}   median R: {med}   sum R: {tot}")

    lines.append("\nOPEN SIGNALS")
    lines.append("-" * 70)
    if not report.open_rows:
        lines.append("  (none)")
    for r in sorted(report.open_rows, key=lambda x: x.emitted_at):
        age_h = (report.generated_at - r.emitted_at).total_seconds() / 3600
        lines.append(
            f"  {r.edge_code}  {r.symbol:<20} entry ${r.entry_price:.6g}  age {age_h:5.1f}h  "
            f"id={r.signal_id}"
        )

    lines.append("\nRESOLVED (most recent 20)")
    lines.append("-" * 70)
    resolved = sorted(
        [r for r in report.rows if r.outcome is not None],
        key=lambda x: x.resolved_at or x.emitted_at,
        reverse=True,
    )[:20]
    if not resolved:
        lines.append("  (none)")
    for r in resolved:
        r_str = f"{r.r_multiple:+.2f}R" if r.r_multiple is not None else "n/a"
        held = f"{r.held_minutes:.0f}m" if r.held_minutes is not None else "—"
        lines.append(
            f"  {r.edge_code}  {r.outcome:<8} {r.symbol:<20} {r_str:>8}  held {held:>6}  "
            f"id={r.signal_id}"
        )

    lines.append("=" * 70)
    return "\n".join(lines)


# ---------- render: HTML -----------------------------------------------


def _esc_html(v: object) -> str:
    from html import escape

    return escape("" if v is None else str(v), quote=True)


def render_html(report: Report) -> str:
    parts: list[str] = []
    parts.append("<!doctype html><html><head><meta charset='utf-8'>")
    parts.append("<title>CodeOracle signal review</title>")
    parts.append("<style>")
    parts.append("body{font:14px/1.4 system-ui,sans-serif;margin:20px;color:#222}")
    parts.append("h1{font-size:18px}h2{font-size:15px;margin-top:24px}")
    parts.append("table{border-collapse:collapse;margin:8px 0;width:100%}")
    parts.append("th,td{padding:4px 8px;border-bottom:1px solid #ddd;text-align:left;vertical-align:top}")
    parts.append("th{background:#f5f5f5;font-weight:600}")
    parts.append(".tp1{color:#080}.sl{color:#c00}.expired{color:#888}.invalid{color:#a0a}")
    parts.append(".open{color:#04a}.num{font-variant-numeric:tabular-nums;text-align:right}")
    parts.append("</style></head><body>")
    parts.append(f"<h1>CodeOracle signal review — last {report.window_days} days</h1>")
    parts.append(
        f"<p>Generated {_esc_html(report.generated_at.isoformat(timespec='seconds'))} · "
        f"total {_esc_html(len(report.rows))} · open {_esc_html(len(report.open_rows))}</p>"
    )

    parts.append("<h2>Per-edge stats</h2>")
    parts.append("<table><tr><th>edge</th><th class='num'>total</th><th class='num'>resolved</th>"
                 "<th class='num'>open</th><th class='num'>invalid</th>"
                 "<th class='num'>TP1</th><th class='num'>SL</th><th class='num'>EXPIRED</th>"
                 "<th class='num'>win rate</th><th class='num'>median R</th><th class='num'>sum R</th></tr>")
    for code in sorted(report.per_edge):
        s = report.per_edge[code]
        win = f"{s.win_rate * 100:.0f}%" if s.win_rate is not None else "—"
        med = f"{s.median_r:+.2f}R" if s.median_r is not None else "—"
        tot = f"{s.total_r:+.2f}R" if s.total_r is not None else "—"
        parts.append(
            f"<tr><td>{_esc_html(code)}</td>"
            f"<td class='num'>{s.n_total}</td>"
            f"<td class='num'>{s.n_resolved}</td>"
            f"<td class='num'>{s.n_open}</td>"
            f"<td class='num'>{s.n_invalid}</td>"
            f"<td class='num'>{s.n_tp1}</td>"
            f"<td class='num'>{s.n_sl}</td>"
            f"<td class='num'>{s.n_expired}</td>"
            f"<td class='num'>{_esc_html(win)}</td>"
            f"<td class='num'>{_esc_html(med)}</td>"
            f"<td class='num'>{_esc_html(tot)}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h2>Open signals</h2>")
    parts.append("<table><tr><th>edge</th><th>symbol</th><th class='num'>entry</th>"
                 "<th class='num'>age (h)</th><th>signal_id</th></tr>")
    for r in sorted(report.open_rows, key=lambda x: x.emitted_at):
        age_h = (report.generated_at - r.emitted_at).total_seconds() / 3600
        parts.append(
            f"<tr class='open'><td>{_esc_html(r.edge_code)}</td>"
            f"<td>{_esc_html(r.symbol)}</td>"
            f"<td class='num'>${r.entry_price:.6g}</td>"
            f"<td class='num'>{age_h:.1f}</td>"
            f"<td>{_esc_html(r.signal_id)}</td></tr>"
        )
    parts.append("</table>")

    parts.append("<h2>Resolved (most recent 50)</h2>")
    parts.append("<table><tr><th>edge</th><th>outcome</th><th>symbol</th>"
                 "<th class='num'>R</th><th class='num'>held (min)</th>"
                 "<th class='num'>entry</th><th class='num'>exit</th><th>signal_id</th></tr>")
    resolved = sorted(
        [r for r in report.rows if r.outcome is not None],
        key=lambda x: x.resolved_at or x.emitted_at, reverse=True,
    )[:50]
    outcome_class = {"TP1": "tp1", "SL": "sl", "EXPIRED": "expired", "INVALID": "invalid"}
    for r in resolved:
        r_str = f"{r.r_multiple:+.2f}" if r.r_multiple is not None else "n/a"
        held = f"{r.held_minutes:.0f}" if r.held_minutes is not None else "—"
        exit_str = f"${r.exit_price:.6g}" if r.exit_price is not None else "—"
        cls = outcome_class.get(r.outcome or "", "")
        parts.append(
            f"<tr class='{cls}'><td>{_esc_html(r.edge_code)}</td>"
            f"<td>{_esc_html(r.outcome)}</td>"
            f"<td>{_esc_html(r.symbol)}</td>"
            f"<td class='num'>{_esc_html(r_str)}</td>"
            f"<td class='num'>{_esc_html(held)}</td>"
            f"<td class='num'>${r.entry_price:.6g}</td>"
            f"<td class='num'>{_esc_html(exit_str)}</td>"
            f"<td>{_esc_html(r.signal_id)}</td></tr>"
        )
    parts.append("</table>")

    parts.append("</body></html>")
    return "".join(parts)
