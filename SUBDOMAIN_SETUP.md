# Arena Subdomain Setup

To point arena.fiftyfund.ai to this Vercel project:

1. Go to your domain registrar (wherever fiftyfund.ai is registered)
2. Add a CNAME record:
   - Name: arena
   - Value: cname.vercel-dns.com
3. Go to Vercel project settings → Domains → Add "arena.fiftyfund.ai"
4. Vercel will auto-provision SSL

After DNS propagates (~5 min), arena.fiftyfund.ai will serve this dashboard.
