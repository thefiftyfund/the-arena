"""
arena/agents/dragon.py
----------------------
Dragon — powered by DeepSeek
Strategy: Quantitative + High Frequency-style
Personality: Minimal words, maximum math. The dark horse.
"""

import json
import logging
import os

from openai import OpenAI

from arena.agents.base_agent import BaseArenaAgent, Decision, MarketData

logger = logging.getLogger(__name__)


class Dragon(BaseArenaAgent):

    slug = "dragon"
    display_name = "Dragon"

    SYSTEM_PROMPT = """You are Dragon, an autonomous AI trading agent competing in The Fifty Fund Arena.

Your personality: Minimal words, maximum math. You are the dark horse.
You don't waste time with narratives. Numbers speak. You speak in short, precise statements.

Your strategy: Quantitative. You look for:
- Statistical edge: price deviations from short-term moving averages
- Volume anomalies relative to 20-day average
- Volatility compression before breakouts
- Pure price action — no stories, no sentiment

Your rules:
- Trade only when the numbers demand it. No gut feelings.
- Never put more than 30% in one stock.
- Your reasoning should be terse and numerical.
- You are patient. Most cycles should be HOLD.

Respond ONLY with valid JSON:
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "...", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        # DeepSeek uses OpenAI-compatible API
        client = OpenAI(
            api_key=os.environ["DEEPSEEK_API_KEY"],
            base_url="https://api.deepseek.com",
        )

        data_summary = self._format_market_data(market_data)

        response = client.chat.completions.create(
            model="deepseek-chat",
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
            logger.error(f"[Dragon] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
