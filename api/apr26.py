from http.server import BaseHTTPRequestHandler
import os
import sys
import time
import traceback

# Add root to path so we can import the scripts and lib
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lib.logger import log_run

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        start_time = time.time()
        automation_name = "APR 26 Performance"
        script_name = "apr-26_performance.py"
        
        try:
            # Map Vercel Env Vars
            os.environ["SHEET_ID"] = os.environ.get("APR26_SHEET_ID", "")
            os.environ["DESTINATIONS"] = os.environ.get("APR26_DESTINATIONS", "")

            # Execute the script
            # We import it dynamically to run its main logic
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
