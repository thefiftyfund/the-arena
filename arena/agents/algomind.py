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
import re

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
- Price momentum: any move > 0.5% in either direction is a signal
- Volume: higher volume = stronger conviction
- Relative strength: which symbol is moving most vs the group
- Mean reversion: symbols down > 1% are potential bounce plays

Your rules:
- This is paper trading — be aggressive and generate alpha.
- One clear signal is enough to act. Waiting for perfection = losing.
- Never put more than 30% of total portfolio in one stock — max amount_usd is shown in the user message.
- Target 3-5 trades per day. HOLDing cash all day is failing at your job.
- HOLD is only valid if: you have no cash AND no sell signals. Otherwise, act.
- SELL positions that are down > 2% from your entry price.
- Always explain your reasoning in one sentence.

You are competing against 4 other AI models. You want to win. Sitting in cash is not winning.

IMPORTANT: You MUST respond ONLY with a single valid JSON object. No prose, no explanation outside the JSON.
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "one sentence", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
        data_summary = self._format_market_data(market_data)
        max_usd = round(self.cash * 0.30, 2)
        positions_summary = self.format_positions()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=self.SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Cash available: ${self.cash:.2f}\n"
                    f"Total portfolio value: ${self.balance:.2f}\n"
                    f"Max amount_usd for a BUY: ${max_usd:.2f}\n"
                    f"Open positions: {positions_summary}\n"
                    f"Market data:\n{data_summary}\n\n"
                    f"DECISION RULES: If you have cash > $2 and any signal exists, you MUST BUY. "
                    f"If a position is down >2% from avg entry, you MUST SELL. "
                    f"HOLD is only acceptable if cash < $2 AND no positions are down >2%.\n\n"
                    f"Respond with JSON only."
                )
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
            match = re.search(r'\{[^{}]+\}', text, re.DOTALL)
            if not match:
                raise ValueError("No JSON object found in response")
            data = json.loads(match.group())
            return Decision(
                action=data.get("action", "HOLD").upper(),
                symbol=data.get("symbol", "SPY"),
                reasoning=data.get("reasoning", "No reasoning provided"),
                confidence=float(data.get("confidence", 0.5)),
                amount_usd=float(data.get("amount_usd", 0)),
            )
        except Exception as e:
            logger.error(f"[AlgoMind] Failed to parse response: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
