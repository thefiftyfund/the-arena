"""
arena/arena_runner.py
---------------------
Main entry point for The Fifty Fund Arena.
Orchestrates all 5 agents on 30-minute cycles during NYSE hours.
Runs roast generator at end of day.

Railway Procfile: worker: python -m arena.arena_runner
"""

import logging
import time
from datetime import datetime, timezone, timedelta

from arena.db import database as db
from arena.agents.algomind import AlgoMind
from arena.agents.oracle import Oracle
from arena.agents.gemini_rising import GeminiRising
from arena.agents.maverick import Maverick
from arena.agents.dragon import Dragon
from arena.roast_generator import generate_daily_roasts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger("arena_runner")

ET = timezone(timedelta(hours=-4))  # Eastern Time (EDT)

MARKET_OPEN_HOUR = 9
MARKET_OPEN_MIN = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MIN = 0
CYCLE_INTERVAL = 1800  # 30 minutes


def is_market_hours(now_et: datetime) -> bool:
    """Check if current time is during NYSE trading hours (Mon-Fri 9:30-16:00 ET)."""
    if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now_et.replace(hour=MARKET_OPEN_HOUR, minute=MARKET_OPEN_MIN, second=0)
    market_close = now_et.replace(hour=MARKET_CLOSE_HOUR, minute=MARKET_CLOSE_MIN, second=0)
    return market_open <= now_et < market_close


def is_end_of_day(now_et: datetime) -> bool:
    """Check if it's just after market close (4:00-4:05 PM ET)."""
    return (now_et.weekday() < 5 and
            now_et.hour == MARKET_CLOSE_HOUR and
            now_et.minute < 5)


def seconds_until_next_cycle(now_et: datetime) -> int:
    """Calculate seconds until next 30-minute boundary."""
    minutes_past = now_et.minute % 30
    seconds_past = minutes_past * 60 + now_et.second
    remaining = CYCLE_INTERVAL - seconds_past
    return max(remaining, 10)  # minimum 10s sleep


def run_all_agents():
    """Run one cycle for all 5 agents sequentially."""
    agents = [AlgoMind(), Oracle(), GeminiRising(), Maverick(), Dragon()]
    results = {}

    for agent in agents:
        try:
            result = agent.run_cycle()
            results[agent.slug] = result
            logger.info(f"✅ {agent.display_name}: {result.get('status', 'unknown')}")
        except Exception as e:
            logger.error(f"❌ {agent.display_name} crashed: {e}", exc_info=True)
            results[agent.slug] = {"status": "error", "error": str(e)}

    return results


def main():
    """Main loop — runs forever on Railway."""
    logger.info("🏟️ The Fifty Fund Arena starting up...")

    db.init_pool()
    funds = db.get_all_funds()
    logger.info(f"Loaded {len(funds)} funds: {[f['name'] for f in funds]}")

    roasts_done_today = False

    while True:
        now_et = datetime.now(ET)

        if is_market_hours(now_et):
            logger.info(f"📈 Market open — running all agents ({now_et.strftime('%H:%M ET')})")
            results = run_all_agents()
            logger.info(f"Cycle complete: {results}")
            roasts_done_today = False  # Reset for new day if needed

            # Sleep until next 30-min boundary
            sleep_sec = seconds_until_next_cycle(now_et)
            logger.info(f"💤 Sleeping {sleep_sec}s until next cycle")
            time.sleep(sleep_sec)

        elif is_end_of_day(now_et) and not roasts_done_today:
            logger.info("🎤 Market closed — generating daily roasts!")
            try:
                roasts = generate_daily_roasts()
                logger.info(f"Generated {len(roasts)} roasts")
                roasts_done_today = True
            except Exception as e:
                logger.error(f"Roast generation failed: {e}", exc_info=True)
            time.sleep(300)  # Wait 5 min before next check

        else:
            # Outside market hours — check every 5 minutes
            day_name = now_et.strftime("%A")
            next_check = 300
            logger.info(
                f"{'Weekend' if now_et.weekday() >= 5 else 'After hours'} "
                f"({now_et.strftime('%H:%M ET %A')}). Next check in {next_check}s."
            )
            time.sleep(next_check)


if __name__ == "__main__":
    main()
