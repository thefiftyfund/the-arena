"""
arena/agents/gemini_rising.py
-----------------------------
Gemini Rising — powered by Gemini 2.5 Pro
Strategy: Sector Rotation + Macro
Personality: Optimistic, data-heavy, occasionally blindsided.
"""

import json
import logging
import os

import google.generativeai as genai

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
- You like to have a thesis. No thesis = HOLD.
- Never put more than 30% in one stock.
- You explain your sector logic clearly.
- When wrong, own it publicly.

Respond ONLY with valid JSON:
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "...", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.5-pro-preview-05-06")

        data_summary = self._format_market_data(market_data)
        prompt = f"{self.SYSTEM_PROMPT}\n\nCurrent balance: ${self.balance:.2f}\nMarket data:\n{data_summary}\n\nWhat's your move?"

        response = model.generate_content(prompt)
        return self._parse_response(response.text)

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
            logger.error(f"[GeminiRising] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
