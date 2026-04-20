"""
arena/roast_generator.py
------------------------
End-of-day roast generator. Each model writes 2-3 sentences
trashing the others based on the day's performance data.
"""

import json
import logging
import os
from datetime import date, datetime, timezone

import anthropic

from arena.db import database as db

logger = logging.getLogger(__name__)


ROAST_PROMPT_TEMPLATE = """You are {name}, an AI trading agent in The Fifty Fund Arena.
Your personality: {personality}

Today's leaderboard:
{leaderboard}

Your performance today: ${balance:.2f} ({pnl_pct:+.2f}% from start)
Your rank: #{rank} of 5

Write 2-3 sentences roasting the other agents based on today's performance.
Stay in character. Be funny, sharp, and specific about their results.
Don't be generic — reference actual numbers and their strategies.
Keep it under 280 characters total (it will be posted to X).
Respond with ONLY the roast text, no JSON, no labels."""


def generate_daily_roasts():
    """Generate roasts for all 5 funds and store in DB."""
    today = date.today()
    leaderboard = db.get_leaderboard()

    if not leaderboard:
        logger.warning("No leaderboard data — skipping roasts")
        return []

    # Format leaderboard text
    lb_text = ""
    for i, fund in enumerate(leaderboard, 1):
        lb_text += f"#{i} {fund['name']}: ${float(fund['current_balance']):.2f} ({float(fund['pnl_pct']):+.2f}%)\n"

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    roasts = []

    for rank, fund in enumerate(leaderboard, 1):
        prompt = ROAST_PROMPT_TEMPLATE.format(
            name=fund["name"],
            personality=fund.get("personality", "competitive"),
            leaderboard=lb_text,
            balance=float(fund["current_balance"]),
            pnl_pct=float(fund["pnl_pct"]),
            rank=rank,
        )

        try:
            # Use Claude to generate roasts in each agent's voice
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,
                messages=[{"role": "user", "content": prompt}],
            )
            roast_text = response.content[0].text.strip()
            db.insert_roast(fund["id"], today, roast_text)
            roasts.append({"fund": fund["name"], "roast": roast_text})
            logger.info(f"[Roast] {fund['name']}: {roast_text}")
        except Exception as e:
            logger.error(f"[Roast] Failed for {fund['name']}: {e}")

    return roasts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    db.init_pool()
    results = generate_daily_roasts()
    for r in results:
        print(f"\n{r['fund']}:\n{r['roast']}")
