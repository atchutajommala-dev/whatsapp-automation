from http.server import BaseHTTPRequestHandler
import os
import sys
import time
import traceback
from urllib.parse import urlparse, parse_qs

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lib.logger import redis, log_run

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start_time = time.time()
        query = parse_qs(urlparse(self.path).query)
        aid = query.get("id", [None])[0]
        
        if not aid:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing automation ID")
            return

        config = redis.hgetall(f"automation:{aid}")
        if not config:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Automation not found in Redis")
            return

        automation_name = config.get("name")
        
        try:
            # Prepare parameters for the master script
            os.environ["SHEET_ID"] = config.get("sheet_id", "")
            os.environ["SHEET_NAME"] = config.get("sheet_name", "")
            os.environ["RANGES"] = config.get("ranges", "")
            os.environ["DESTINATIONS"] = config.get("destinations", "")

            # Execute the Master Script
            import master_automation
            import importlib
            importlib.reload(master_automation) # Ensure clean state
            
            master_automation.run_automation(
                sheet_id=os.environ["SHEET_ID"],
                sheet_name=os.environ["SHEET_NAME"],
                ranges=os.environ["RANGES"].split(","),
                destinations=os.environ["DESTINATIONS"].split(",")
            )
            
            duration = time.time() - start_time
            log_run(automation_name, "success", "Master Automation completed.", duration)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Success: {automation_name} triggered.".encode())
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = traceback.format_exc()
            log_run(automation_name, "error", error_msg, duration)
            
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())
