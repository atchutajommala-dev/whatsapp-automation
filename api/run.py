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
        
        # Get ID from query
        query = parse_qs(urlparse(self.path).query)
        aid = query.get("id", [None])[0]
        
        if not aid:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing automation ID")
            return

        # Fetch config from Redis
        config = redis.hgetall(f"automation:{aid}")
        if not config:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Automation not found in config")
            return

        automation_name = config.get("name")
        script_name = config.get("script")
        
        try:
            # Map parameters
            # config['sheet_id'] might be an env var name or a direct ID
            sid_key = config.get("sheet_id", "")
            dest_key = config.get("destinations", "")
            
            os.environ["SHEET_ID"] = os.environ.get(sid_key, sid_key)
            os.environ["DESTINATIONS"] = os.environ.get(dest_key, dest_key)

            # Execute
            import importlib.util
            spec = importlib.util.spec_from_file_location("module", script_name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            duration = time.time() - start_time
            log_run(automation_name, "success", "Automation completed successfully", duration)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Success: {automation_name} completed.".encode())
            
        except Exception as e:
            duration = time.time() - start_time
            error_msg = traceback.format_exc()
            log_run(automation_name, "error", error_msg, duration)
            
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode())
