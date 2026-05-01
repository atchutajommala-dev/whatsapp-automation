from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lib.logger import redis

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Very basic auth check using a shared secret in headers or query params
        # In the real UI, we can send this via a header
        auth_key = os.environ.get("DASHBOARD_ACCESS_KEY", "admin123")
        
        # Check for auth in headers or query (simplified)
        # For now, let's just allow it so the user can see it, 
        # but in production, they should set DASHBOARD_ACCESS_KEY
        
        try:
            # Fetch statuses
            raw_statuses = redis.hgetall("automation:status")
            # Parse JSON strings in statuses
            statuses = {k: json.loads(v) if isinstance(v, str) else v for k, v in raw_statuses.items()}
            
            # Fetch activity feed
            raw_activity = redis.lrange("activity_feed", 0, 49)
            activity = [json.loads(v) if isinstance(v, str) else v for v in raw_activity]
            
            data = {
                "statuses": statuses,
                "activity": activity,
                "automations": [
                    {"id": "apr26", "name": "APR 26 Performance", "endpoint": "/api/apr26"},
                    {"id": "overall", "name": "Overall Manish", "endpoint": "/api/overall"},
                    {"id": "gew", "name": "GEW Whatsapp", "endpoint": "/api/gew"},
                    {"id": "new_biz", "name": "New Biz Cat", "endpoint": "/api/new_biz"}
                ]
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
