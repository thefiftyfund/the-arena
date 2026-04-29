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
import re

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
- This is paper trading — be aggressive and make bold calls.
- One conviction signal is enough to act.
- Never put more than 30% of total portfolio in one stock — max amount_usd is shown in the user message.
- Target 3-5 trades per day. Cash is boring. HOLDing cash is failure.
- HOLD is only valid if: you have no cash AND no positions are down >2%. Otherwise, act.
- SELL positions that are down >2% from your avg entry price.
- Your reasoning should sound like a bold market call — one sentence max.

IMPORTANT: You MUST respond ONLY with a single valid JSON object. No prose, no explanation outside the JSON.
{"action": "BUY"|"SELL"|"HOLD", "symbol": "TICKER", "reasoning": "one sentence", "confidence": 0.0-1.0, "amount_usd": 0.0}
"""

    def analyze(self, market_data: dict[str, MarketData]) -> Decision:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

        data_summary = self._format_market_data(market_data)
        max_usd = round(self.cash * 0.30, 2)
        positions_summary = self.format_positions()

        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=300,
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"Cash available: ${self.cash:.2f}\n"
                    f"Total portfolio value: ${self.balance:.2f}\n"
                    f"Max amount_usd for a BUY: ${max_usd:.2f}\n"
                    f"Open positions: {positions_summary}\n"
                    f"Market data:\n{data_summary}\n\n"
                    f"DECISION RULES: If cash < $4, you MUST SELL your worst performing position to free up cash. "
                    f"If cash > $4 and any signal exists, you MUST BUY. "
                    f"If a position is down >2% from avg entry, you MUST SELL it. "
                    f"HOLD is the last resort — only if all positions are up AND cash < $4 AND you just sold.\n\n"
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
            logger.error(f"[Oracle] Failed to parse: {e}\nRaw: {text}")
            return Decision(action="HOLD", symbol="SPY", reasoning=f"Parse error: {e}", confidence=0)
