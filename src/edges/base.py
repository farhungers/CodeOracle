"""Edge ABC and Signal dataclass. Concrete edges live in sibling modules."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Signal:
    """Emitted by an edge evaluator. Matches signals table columns from
    src/db/migrations/002_signals.sql (subset — the writer fills in ts,
    tg_message_id, tg_chat_id, medal after emission-gate composition).
    """

    edge_code: str
    chain: str
    token_addr: str
    symbol: str
    direction: str  # 'long' | 'short_advisory' | 'short_perp'
    entry_price: float
    stop_price: float
    tp1_price: float
    thesis_window_min: int
    entry_window_min: int
    reasons: list[str] = field(default_factory=list)   # "WHY THIS SETUP" bullets
    card_extras: dict[str, Any] = field(default_factory=dict)   # payload for full card render
    thesis_narrative: str = ""                          # WHY block: one-sentence thesis
    thesis_evidence: str = ""                           # WHY block: one distinguishing evidence bullet


class Edge(ABC):
    """Concrete edges implement evaluate(states, cycle_ctx) -> list[Signal].

    States is the enriched, GATE-ZERO-annotated token list from the snapshotter.
    Edges filter to survivors on their own (do not rely on the caller to have
    already dropped failers), so they can also express filter behavior that
    diverges from GATE ZERO (e.g., E1's stricter top-10 threshold).
    """

    code: str
    version: int = 1

    @abstractmethod
    def evaluate(self, states: list, cycle_ctx: dict) -> list[Signal]:  # noqa: ANN001
        raise NotImplementedError
