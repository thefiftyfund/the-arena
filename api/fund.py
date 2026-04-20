"""
GET /api/fund?slug=algomind
Returns full detail for a single fund: info, positions, recent trades.
"""
import json
import os
from urllib.parse import urlparse, parse_qs
import psycopg2
from psycopg2.extras import RealDictCursor
from http.server import BaseHTTPRequestHandler


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


def serialize(row):
    result = {}
    for k, v in row.items():
        if hasattr(v, 'isoformat'):
            result[k] = v.isoformat()
        elif isinstance(v, (int, float, bool, str, type(None))):
            result[k] = v
        else:
            result[k] = float(v)
    return result


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            slug = params.get("slug", [None])[0]

            if not slug:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "slug parameter required"}).encode())
                return

            conn = get_connection()
            cur = conn.cursor()

            # Fund info
            cur.execute("""
                SELECT *, 
                    ROUND(((current_balance - starting_balance) / starting_balance) * 100, 2) AS pnl_pct,
                    (current_balance - starting_balance) AS pnl_abs
                FROM funds WHERE slug = %s
            """, (slug,))
            fund = cur.fetchone()

            if not fund:
                conn.close()
                self.send_response(404)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "fund not found"}).encode())
                return

            # Positions
            cur.execute("""
                SELECT symbol, shares, avg_price, current_price, updated_at
                FROM positions
                WHERE fund_id = %s AND shares > 0
                ORDER BY symbol
            """, (fund['id'],))
            positions = cur.fetchall()

            # Recent trades
            cur.execute("""
                SELECT id, cycle_id, symbol, action, shares, price, reasoning, created_at
                FROM trades
                WHERE fund_id = %s
                ORDER BY created_at DESC
                LIMIT 30
            """, (fund['id'],))
            trades = cur.fetchall()

            # Latest roast
            cur.execute("""
                SELECT content, roast_date
                FROM roasts
                WHERE fund_id = %s
                ORDER BY roast_date DESC
                LIMIT 1
            """, (fund['id'],))
            roast = cur.fetchone()

            conn.close()

            result = {
                "fund": serialize(fund),
                "positions": [serialize(p) for p in positions],
                "trades": [serialize(t) for t in trades],
                "latest_roast": serialize(roast) if roast else None
            }

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
