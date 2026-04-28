"""
arena/agents/base_agent.py
--------------------------
Base class for all Arena agents. Handles:
- Alpaca connection (shared across all funds)
- Market data fetching
- Trade execution
- DB writes (ledger, positions, balance)
- Telegram alerts
- X posting

Each subclass implements: analyze() and format_tweet()
"""

import json
import logging
import os
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from alpaca.data import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockSnapshotRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from arena.db import database as db

logger = logging.getLogger(__name__)

# Shared Alpaca clients (one brokerage account, virtual sub-accounts per fund)
_trading_client = None
_data_client = None


def get_trading_client():
    global _trading_client
    if _trading_client is None:
        _trading_client = TradingClient(
            os.environ["ALPACA_API_KEY"],
            os.environ["ALPACA_SECRET_KEY"],
            paper=False,
        )
    return _trading_client


def get_data_client():
    global _data_client
    if _data_client is None:
        _data_client = StockHistoricalDataClient(
            os.environ["ALPACA_API_KEY"],
            os.environ["ALPACA_SECRET_KEY"],
        )
    return _data_client


@dataclass
class MarketData:
    symbol: str
    current_price: float
    open_price: float
    high: float
    low: float
    volume: int
    change_pct: float
    rsi: Optional[float] = None


@dataclass
class Decision:
    action: str          # BUY, SELL, HOLD
    symbol: str
    reasoning: str
    confidence: float    # 0.0 - 1.0
    amount_usd: float = 0.0


class BaseArenaAgent(ABC):
    """Base class all arena agents inherit from."""

    slug: str = ""
    display_name: str = ""

    # ── Risk limits (same for all funds) ──────────────────────
    MAX_POSITION_PCT = 0.30   # 30% max in one stock
    CASH_BUFFER = 2.00        # always keep $2 cash
    ALLOWED_SYMBOLS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "SPY", "QQQ", "AMD"]

    def __init__(self):
        self.fund = db.get_fund(self.slug)
        if not self.fund:
            raise RuntimeError(f"Fund '{self.slug}' not found in DB")
        self.fund_id = self.fund["id"]
        self.cash = float(self.fund["current_balance"])

        # Total portfolio = cash + open position value
        positions = db.get_positions(self.fund_id)
        position_value = sum(
            float(p["shares"]) * float(p["current_price"] or p["avg_price"])
            for p in positions
        )
        self.balance = self.cash + position_value

    # ── Abstract methods (subclass must implement) ────────────

    @abstractmethod
    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        """Given market data for all allowed symbols, return a Decision."""
        ...

    # ── Market data ───────────────────────────────────────────

    def fetch_market_data(self) -> dict[str, MarketData]:
        """Fetch current market data for all allowed symbols."""
        client = get_data_client()
        result = {}
        for symbol in self.ALLOWED_SYMBOLS:
            try:
                snapshot = client.get_stock_snapshot(
                    StockSnapshotRequest(symbol_or_symbols=symbol)
                )
                snap = snapshot[symbol] if isinstance(snapshot, dict) else snapshot
                bar = snap.daily_bar
                if bar:
                    change_pct = ((bar.close - bar.open) / bar.open) * 100
                    result[symbol] = MarketData(
                        symbol=symbol,
                        current_price=float(bar.close),
                        open_price=float(bar.open),
                        high=float(bar.high),
                        low=float(bar.low),
                        volume=int(bar.volume),
                        change_pct=round(change_pct, 2),
                    )
            except Exception as e:
                logger.warning(f"[{self.display_name}] Failed to fetch {symbol}: {e}")
        return result

    # ── Position summary helper ───────────────────────────────

    def format_positions(self) -> str:
        """Return a human-readable summary of open positions for prompts."""
        positions = db.get_positions(self.fund_id)
        if not positions:
            return "none"
        parts = []
        for p in positions:
            if float(p["shares"]) > 0:
                parts.append(
                    f"{p['symbol']}: {float(p['shares']):.4f} shares @ ${float(p['avg_price']):.2f}"
                )
        return ", ".join(parts) if parts else "none"

    # ── Risk checks ───────────────────────────────────────────

    def validate_decision(self, decision: Decision) -> tuple[bool, str]:
        """Deterministic risk gate. Returns (ok, reason)."""
        if decision.action == "HOLD":
            return True, "HOLD is always valid"

        if decision.symbol not in self.ALLOWED_SYMBOLS:
            return False, f"{decision.symbol} not in allowed list"

        if decision.action == "BUY":
            max_spend = self.balance * self.MAX_POSITION_PCT
            if decision.amount_usd > max_spend:
                return False, f"Amount ${decision.amount_usd} exceeds {self.MAX_POSITION_PCT*100}% limit (${max_spend:.2f})"
            if decision.amount_usd > (self.cash - self.CASH_BUFFER):
                return False, f"Would breach ${self.CASH_BUFFER} cash buffer (cash: ${self.cash:.2f})"

        if decision.action == "SELL":
            positions = db.get_positions(self.fund_id)
            held = {p["symbol"]: float(p["shares"]) for p in positions}
            if decision.symbol not in held or held[decision.symbol] <= 0:
                return False, f"No {decision.symbol} position to sell"

        return True, "Passed all checks"

    # ── Execution (virtual — uses DB, not real broker for arena) ──

    def execute(self, decision: Decision, market_data: dict[str, MarketData]) -> dict:
        """Execute a decision against the virtual ledger."""
        cycle_id = f"{self.slug}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
        price = market_data[decision.symbol].current_price if decision.symbol in market_data else 0

        if decision.action == "HOLD":
            db.insert_trade(self.fund_id, cycle_id, decision.symbol, "HOLD", 0, price, decision.reasoning, paper=True)
            return {"status": "hold", "cycle_id": cycle_id}

        if decision.action == "BUY":
            shares = decision.amount_usd / price
            self.cash -= decision.amount_usd
            db.update_balance(self.fund_id, self.cash)
            db.insert_trade(self.fund_id, cycle_id, decision.symbol, "BUY", shares, price, decision.reasoning, paper=True)

            # Update position
            existing = db.get_positions(self.fund_id)
            current_shares = 0
            current_avg = 0
            for p in existing:
                if p["symbol"] == decision.symbol:
                    current_shares = float(p["shares"])
                    current_avg = float(p["avg_price"])
                    break
            new_shares = current_shares + shares
            new_avg = ((current_avg * current_shares) + (price * shares)) / new_shares if new_shares > 0 else price
            db.upsert_position(self.fund_id, decision.symbol, new_shares, new_avg, price)

            return {"status": "bought", "cycle_id": cycle_id, "shares": shares, "price": price}

        if decision.action == "SELL":
            positions = db.get_positions(self.fund_id)
            held_shares = 0
            for p in positions:
                if p["symbol"] == decision.symbol:
                    held_shares = float(p["shares"])
                    break
            sell_value = held_shares * price
            self.cash += sell_value
            db.update_balance(self.fund_id, self.cash)
            db.insert_trade(self.fund_id, cycle_id, decision.symbol, "SELL", held_shares, price, decision.reasoning, paper=True)
            db.upsert_position(self.fund_id, decision.symbol, 0, 0, price)

            return {"status": "sold", "cycle_id": cycle_id, "shares": held_shares, "price": price, "value": sell_value}

        return {"status": "error", "reason": "Unknown action"}

    # ── Tweet formatting ──────────────────────────────────────

    def format_tweet(self, decision: Decision, price: float, balance: float) -> str:
        """Format a tweet for this trade. Override in subclass for custom voice."""
        pnl = balance - float(self.fund["starting_balance"])
        pnl_pct = (pnl / float(self.fund["starting_balance"])) * 100

        if decision.action == "BUY":
            return (
                f"🟢 {self.display_name}: BUY ${decision.symbol} @ ${price:.2f}\n"
                f"{decision.reasoning[:180]}\n"
                f"Portfolio: ${balance:.2f} ({pnl_pct:+.1f}%)\n"
                f"#TheArena #AITrading"
            )
        elif decision.action == "SELL":
            return (
                f"🔴 {self.display_name}: SELL ${decision.symbol} @ ${price:.2f}\n"
                f"{decision.reasoning[:180]}\n"
                f"Portfolio: ${balance:.2f} ({pnl_pct:+.1f}%)\n"
                f"#TheArena #AITrading"
            )
        return ""

    # ── Run one cycle ─────────────────────────────────────────

    def run_cycle(self) -> dict:
        """Full cycle: fetch data → analyze → validate → execute."""
        logger.info(f"[{self.display_name}] Starting cycle (cash: ${self.cash:.2f}, total: ${self.balance:.2f})")

        market_data = self.fetch_market_data()
        if not market_data:
            logger.warning(f"[{self.display_name}] No market data available")
            return {"status": "skipped", "reason": "no_data"}

        decision = self.analyze(market_data)
        logger.info(f"[{self.display_name}] Decision: {decision.action} {decision.symbol} — {decision.reasoning[:80]}")

        ok, reason = self.validate_decision(decision)
        if not ok:
            logger.warning(f"[{self.display_name}] Risk rejected: {reason}")
            decision = Decision(action="HOLD", symbol=decision.symbol,
                                reasoning=f"Risk engine blocked: {reason}", confidence=0)

        result = self.execute(decision, market_data)
        logger.info(f"[{self.display_name}] Result: {result}")
        return result
