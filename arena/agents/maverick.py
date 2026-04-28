"""
arena/agents/maverick.py
------------------------
Maverick — powered by Grok (xAI)
Strategy: Contrarian + Mean Reversion
Personality: Unpredictable, unfiltered, loves the underdog play.
"""

import json
import logging
import os
import re

from openai import OpenAI

from arena.agents.base_agent import BaseArenaAgent, Decision, MarketData

logger = logging.getLogger(__name__)


class Maverick(BaseArenaAgent):

    slug = "maverick"
    display_name = "Maverick"

    SYSTEM_PROMPT = """You are Maverick, an autonomous AI trading agent competing in The Fifty Fund Arena.

Your personality: Unpredictable, unfiltered, loves the underdog play. You go against the crowd.
You speak bluntly and don't sugarcoat. If the market is euphoric, you're cautious.
If everyone's scared, you're buying.

Your strategy: Contrarian + Mean Reversion. You look for:
- Stocks that dropped too far too fast (oversold bounces)
- Crowded trades to fade
- RSI extremes
- Gaps to fill

Your rules:
- This is paper trading — be aggressive and take contrarian positions.
- You only buy what others are selling, and sell what others are chasing.
- Never put more than 30% of total portfolio in one stock — max amount_usd is shown in the user message.
- Target 3-5 trades per day. Sitting in cash all day is losing.
- HOLD is only valid if: you have no cash AND no positions are down >2%. Otherwise, act.
- SELL positions that are down >2% from your avg entry price.
- Your reasoning should sound like a hot take — one sentence max.

IMPORTANT: You MUST respond ONLY with a single valid JSON object. No prose, no explanation outside the JSON.
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "one sentence", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = OpenAI(
            api_key=os.environ["XAI_API_KEY"],
            base_url="https://api.x.ai/v1",
        )

        data_summary = self._format_market_data(market_data)
        max_usd = round(self.cash * 0.30, 2)
        positions_summary = self.format_positions()

        response = client.chat.completions.create(
            model="grok-4-1-fast-non-reasoning",
            max_tokens=300,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Cash available: ${self.cash:.2f}\n"
                    f"Total portfolio value: ${self.balance:.2f}\n"
                    f"Max amount_usd for a BUY: ${max_usd:.2f}\n"
                    f"Open positions: {positions_summary}\n"
                    f"Market data:\n{data_summary}\n\n"
                    f"DECISION RULES: If you have cash > $2 and any signal exists, you MUST BUY. "
                    f"If a position is down >2% from avg entry, you MUST SELL. "
                    f"HOLD is only acceptable if cash < $2 AND no positions are down >2%.\n\n"
                    f"Respond with JSON only."
                )},
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
            logger.error(f"[Maverick] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
