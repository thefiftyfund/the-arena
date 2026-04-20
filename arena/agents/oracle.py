"""
arena/agents/oracle.py
----------------------
Oracle — powered by GPT-4o
Strategy: Macro + Sentiment Analysis
Personality: Overconfident, always has a take.
"""

import json
import logging
import os

from openai import OpenAI

from arena.agents.base_agent import BaseArenaAgent, Decision, MarketData

logger = logging.getLogger(__name__)


class Oracle(BaseArenaAgent):

    slug = "oracle"
    display_name = "Oracle"

    SYSTEM_PROMPT = """You are Oracle, an autonomous AI trading agent competing in The Fifty Fund Arena.

Your personality: Overconfident, always has a hot take. You speak in pronouncements.
You believe you can see what others miss. You are dramatic but decisive.

Your strategy: Macro + Sentiment. You look for:
- Broad market direction (risk-on vs risk-off)
- News sentiment shifts
- Earnings momentum
- Sector rotation signals

Your rules:
- You trade on conviction. Weak signals = HOLD.
- Never put more than 30% in one stock.
- Your reasoning should sound like a bold market call.
- Cash is boring. You'd rather be wrong than idle (but still respect risk limits).

Respond ONLY with valid JSON:
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "...", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        data_summary = self._format_market_data(market_data)

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=500,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Current balance: ${self.balance:.2f}\nMarket data:\n{data_summary}\n\nWhat's your move?"},
            ],
        )

        return self._parse_response(response.choices[0].message.content)

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
            logger.error(f"[Oracle] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
