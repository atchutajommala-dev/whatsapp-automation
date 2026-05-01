from http.server import BaseHTTPRequestHandler
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lib.logger import redis, get_automations, save_automation, delete_automation

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            # Fetch Dynamic Automations
            automations = get_automations()
            
            # Fetch statuses
            raw_statuses = redis.hgetall("automation:status")
            statuses = {k: json.loads(v) if isinstance(v, str) else v for k, v in raw_statuses.items()}
            
            # Fetch activity feed
            raw_activity = redis.lrange("activity_feed", 0, 49)
            activity = [json.loads(v) if isinstance(v, str) else v for v in raw_activity]
            
            data = {
                "statuses": statuses,
                "activity": activity,
                "automations": automations
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

    def do_POST(self):
        """Add or Update an automation."""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = json.loads(self.rfile.read(content_length))
            
            if "id" not in post_data:
                # Generate simple ID if missing
                post_data["id"] = post_data["name"].lower().replace(" ", "_")
            
            save_automation(post_data)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "success"}).encode())
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    def do_DELETE(self):
        """Remove an automation."""
        try:
            # Extract ID from path /api/dashboard?id=...
            from urllib.parse import urlparse, parse_qs
            query = parse_qs(urlparse(self.path).query)
            aid = query.get("id", [None])[0]
            
            if aid:
                delete_automation(aid)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Deleted")
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Missing ID")
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())

    # Add OPTIONS for CORS if needed
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
