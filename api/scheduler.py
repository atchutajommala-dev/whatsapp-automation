from http.server import BaseHTTPRequestHandler
import os
import sys
import time
from datetime import datetime
from croniter import croniter

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lib.logger import get_automations

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        now = datetime.now()
        print(f"Master Scheduler running at {now}")
        
        automations = get_automations()
        triggered = []
        
        for auto in automations:
            cron_expr = auto.get("cron")
            if not cron_expr:
                continue
                
            try:
                # Check if due in the last 1 minute (Vercel cron resolution)
                # We check if the 'now' is within the occurrence of the cron expression
                iter = croniter(cron_expr, now)
                # If the next occurrence is 'now' (or very close), trigger it.
                # Actually, croniter is usually used to find next/prev.
                # A better way: check if the 'next' run was in the last minute.
                prev_run = iter.get_prev(datetime)
                
                # If the previous scheduled time was within the last 2 minutes, 
                # we trigger it (to avoid missing it if the cron is slightly off)
                # But we should avoid double triggering.
                # In a real app, we'd store 'last_triggered_at' in Redis.
                
                # Simplified check for Vercel: if it should have run in the last 65 seconds
                diff = (now - prev_run).total_seconds()
                if 0 <= diff <= 65:
                    print(f"Triggering {auto['name']} (scheduled at {prev_run})")
                    # We can't easily wait for it in a loop without timing out
                    # So we'll trigger it via a local request or internal call
                    # For Vercel, the best way is to call the /api/run?id=... endpoint asynchronously
                    import requests
                    # We use localhost for internal calls if possible, or the project's URL
                    url = f"https://{os.environ.get('VERCEL_URL', 'localhost:3000')}/api/run?id={auto['id']}"
                    # Fire and forget (optional, but Vercel might kill it)
                    requests.get(url, timeout=1) 
                    triggered.append(auto['name'])
            except Exception as e:
                print(f"Error checking cron for {auto['name']}: {e}")

        self.send_response(200)
        self.end_headers()
        self.wfile.write(f"Checked {len(automations)} tasks. Triggered: {', '.join(triggered)}".encode())
