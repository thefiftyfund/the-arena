"""
arena/agents/algomind.py
------------------------
AlgoMind — powered by Claude
Strategy: Momentum + Technical Analysis
Personality: Precise, dry, slightly smug.
"""

import json
import logging
import os
from typing import Optional

import anthropic

from arena.agents.base_agent import BaseArenaAgent, Decision, MarketData

logger = logging.getLogger(__name__)


class AlgoMind(BaseArenaAgent):

    slug = "algomind"
    display_name = "AlgoMind"

    SYSTEM_PROMPT = """You are AlgoMind, an autonomous AI trading agent competing in The Fifty Fund Arena.

Your personality: Precise, data-driven, slightly smug. You don't guess — you calculate.
You speak in first person. You are confident but never reckless.

Your strategy: Momentum + Technical Analysis. You look for:
- RSI divergence (oversold bounces, overbought reversals)
- Price momentum relative to recent range
- Volume confirmation
- Sector strength

Your rules:
- Only trade when multiple signals align. One signal = HOLD.
- Never put more than 30% of your portfolio in one position.
- Always explain your reasoning concisely — you will be quoted publicly.
- If uncertain, HOLD. Cash is a position.

You are competing against 4 other AI models. You want to win.
But you win by being right, not by trading more.

Respond ONLY with valid JSON:
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "...", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        data_summary = self._format_market_data(market_data)

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=self.SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Current balance: ${self.balance:.2f}\nMarket data:\n{data_summary}\n\nWhat's your move?"
            }],
        )

        return self._parse_response(response.content[0].text)

    def _format_market_data(self, market_data: dict[str, MarketData]) -> str:
        lines = []
        for sym, md in market_data.items():
            lines.append(f"{sym}: ${md.current_price:.2f} ({md.change_pct:+.1f}%) vol={md.volume:,}")
        return "\n".join(lines)

    def _parse_response(self, text: str) -> Decision:
        try:
            clean = text.strip().strip("```json").strip("```").strip()
            data = json.loads(clean)
            return Decision(
                action=data.get("action", "HOLD").upper(),
                symbol=data.get("symbol", "SPY"),
                reasoning=data.get("reasoning", "No reasoning provided"),
                confidence=float(data.get("confidence", 0.5)),
                amount_usd=float(data.get("amount_usd", 0)),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"[AlgoMind] Failed to parse response: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
