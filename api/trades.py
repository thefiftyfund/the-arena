"""
GET /api/trades
Returns recent trades across all funds.
Optional query params: ?fund=slug&limit=50
"""
import json
import os
from urllib.parse import urlparse, parse_qs
import psycopg2
from psycopg2.extras import RealDictCursor
from http.server import BaseHTTPRequestHandler


def get_connection():
    return psycopg2.connect(os.environ["DATABASE_URL"], cursor_factory=RealDictCursor)


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            fund_slug = params.get("fund", [None])[0]
            limit = min(int(params.get("limit", [50])[0]), 200)

            conn = get_connection()
            cur = conn.cursor()

            if fund_slug:
                cur.execute("""
                    SELECT t.id, t.cycle_id, t.symbol, t.action, t.shares, t.price,
                           t.reasoning, t.created_at, f.name AS fund_name, f.slug AS fund_slug
                    FROM trades t
                    JOIN funds f ON t.fund_id = f.id
                    WHERE f.slug = %s
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (fund_slug, limit))
            else:
                cur.execute("""
                    SELECT t.id, t.cycle_id, t.symbol, t.action, t.shares, t.price,
                           t.reasoning, t.created_at, f.name AS fund_name, f.slug AS fund_slug
                    FROM trades t
                    JOIN funds f ON t.fund_id = f.id
                    ORDER BY t.created_at DESC
                    LIMIT %s
                """, (limit,))

            trades = cur.fetchall()
            conn.close()

            result = []
            for t in trades:
                row = {}
                for k, v in t.items():
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
            self.send_header("Cache-Control", "s-maxage=30, stale-while-revalidate")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())
