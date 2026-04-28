"""
GET /api/leaderboard
Returns all 5 funds ranked by total portfolio value (cash + open positions).
"""
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from http.server import BaseHTTPRequestHandler


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            conn = get_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT
                    f.id,
                    f.slug,
                    f.name,
                    f.model,
                    f.provider,
                    f.strategy,
                    f.personality,
                    f.starting_balance,
                    f.current_balance AS cash,
                    COALESCE(SUM(p.shares * p.current_price), 0) AS position_value,
                    f.current_balance + COALESCE(SUM(p.shares * p.current_price), 0) AS current_balance,
                    ROUND(
                        ((f.current_balance + COALESCE(SUM(p.shares * p.current_price), 0) - f.starting_balance)
                        / f.starting_balance) * 100, 2
                    ) AS pnl_pct,
                    (f.current_balance + COALESCE(SUM(p.shares * p.current_price), 0) - f.starting_balance) AS pnl_abs,
                    COALESCE(t.trade_count, 0) AS trade_count,
                    COALESCE(t.last_trade_at, f.created_at) AS last_trade_at
                FROM funds f
                LEFT JOIN positions p ON p.fund_id = f.id AND p.shares > 0
                LEFT JOIN (
                    SELECT fund_id,
                           COUNT(*) AS trade_count,
                           MAX(created_at) AS last_trade_at
                    FROM trades
                    WHERE action != 'HOLD'
                    GROUP BY fund_id
                ) t ON f.id = t.fund_id
                WHERE f.is_active = TRUE
                GROUP BY f.id, f.slug, f.name, f.model, f.provider, f.strategy,
                         f.personality, f.starting_balance, f.current_balance,
                         t.trade_count, t.last_trade_at
                ORDER BY pnl_pct DESC
            """)
            funds = cur.fetchall()
            conn.close()

            # Convert Decimals to floats for JSON
            result = []
            for f in funds:
                row = {}
                for k, v in f.items():
                    if hasattr(v, 'isoformat'):
                        row[k] = v.isoformat()
                    elif isinstance(v, (int, float, bool, str, type(None))):
                        row[k] = v
                    else:
                        row[k] = float(v)
                result.append(row)

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "s-maxage=60, stale-while-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
