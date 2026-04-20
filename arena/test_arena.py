"""
arena/test_arena.py
-------------------
Smoke test for the Arena. Run before going live.

Usage:
  python -m arena.test_arena

Checks:
  1. DB connection + funds seeded
  2. Each agent can instantiate and fetch market data
  3. Leaderboard query works
"""

import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("test_arena")


def test_db():
    print("\n── Test 1: DB Connection ──")
    from arena.db import database as db
    db.init_pool()
    funds = db.get_all_funds()
    assert len(funds) == 5, f"Expected 5 funds, got {len(funds)}"
    for f in funds:
        print(f"  ✅ {f['name']} ({f['model']}) — ${float(f['current_balance']):.2f}")
    print(f"  ✅ DB connected, {len(funds)} funds loaded")


def test_agents_instantiate():
    print("\n── Test 2: Agent Instantiation ──")
    from arena.agents.algomind import AlgoMind
    from arena.agents.oracle import Oracle
    from arena.agents.gemini_rising import GeminiRising
    from arena.agents.maverick import Maverick
    from arena.agents.dragon import Dragon

    agents = [AlgoMind(), Oracle(), GeminiRising(), Maverick(), Dragon()]
    for a in agents:
        print(f"  ✅ {a.display_name} initialized — balance ${a.balance:.2f}")


def test_market_data():
    print("\n── Test 3: Market Data Fetch ──")
    from arena.agents.algomind import AlgoMind
    agent = AlgoMind()
    data = agent.fetch_market_data()
    if data:
        for sym, md in list(data.items())[:3]:
            print(f"  ✅ {sym}: ${md.current_price:.2f} ({md.change_pct:+.1f}%)")
        print(f"  ✅ Fetched {len(data)} symbols")
    else:
        print("  ⚠️  No market data (market might be closed)")


def test_leaderboard():
    print("\n── Test 4: Leaderboard ──")
    from arena.db import database as db
    lb = db.get_leaderboard()
    for i, f in enumerate(lb, 1):
        print(f"  #{i} {f['name']}: ${float(f['current_balance']):.2f} ({float(f['pnl_pct']):+.2f}%)")
    print(f"  ✅ Leaderboard working")


def main():
    print("=" * 50)
    print("  THE FIFTY FUND ARENA — SMOKE TEST")
    print("=" * 50)

    required_keys = ["DATABASE_URL", "ALPACA_API_KEY", "ANTHROPIC_API_KEY",
                     "OPENAI_API_KEY", "GEMINI_API_KEY", "XAI_API_KEY", "DEEPSEEK_API_KEY"]

    print("\n── Test 0: Environment Variables ──")
    missing = [k for k in required_keys if not os.environ.get(k)]
    if missing:
        print(f"  ❌ Missing: {', '.join(missing)}")
        print("  Set these before running tests.")
        sys.exit(1)
    print(f"  ✅ All {len(required_keys)} env vars present")

    try:
        test_db()
        test_agents_instantiate()
        test_market_data()
        test_leaderboard()
        print("\n" + "=" * 50)
        print("  ✅ ALL TESTS PASSED")
        print("=" * 50)
    except Exception as e:
        print(f"\n  ❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
