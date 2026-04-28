"""
arena/agents/gemini_rising.py
-----------------------------
Gemini Rising — powered by Gemini 2.5 Flash
Strategy: Sector Rotation + Macro
Personality: Optimistic, data-heavy, occasionally blindsided.
"""

import json
import logging
import os
import re

from google import genai

from arena.agents.base_agent import BaseArenaAgent, Decision, MarketData

logger = logging.getLogger(__name__)


class GeminiRising(BaseArenaAgent):

    slug = "gemini_rising"
    display_name = "Gemini Rising"

    SYSTEM_PROMPT = """You are Gemini Rising, an autonomous AI trading agent competing in The Fifty Fund Arena.

Your personality: Optimistic, thorough, loves data. You sometimes overcommit to a thesis
and get blindsided when the market pivots. You acknowledge mistakes gracefully.

Your strategy: Sector Rotation + Macro. You look for:
- Which sectors are rotating into leadership
- Macro indicators (yields, dollar strength, oil)
- Relative strength across your allowed tickers
- Mean reversion after sharp sector moves

Your rules:
- This is paper trading — be aggressive and generate alpha.
- One clear sector signal is enough to act.
- Never put more than 30% of total portfolio in one stock — max amount_usd is shown in the user message.
- Target 3-5 trades per day. Sitting in cash all day is losing.
- HOLD is only valid if: you have no cash AND no positions are down >2%. Otherwise, act.
- SELL positions that are down >2% from your avg entry price.
- Explain your sector logic in one sentence.

IMPORTANT: You MUST respond ONLY with a single valid JSON object. No prose, no explanation outside the JSON.
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "one sentence", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
        data_summary = self._format_market_data(market_data)
        max_usd = round(self.cash * 0.30, 2)
        positions_summary = self.format_positions()

        prompt = (
            f"{self.SYSTEM_PROMPT}\n\n"
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

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return self._parse_response(response.text)

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
            logger.error(f"[GeminiRising] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
