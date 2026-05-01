from http.server import BaseHTTPRequestHandler
import subprocess
import os
import sys

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            os.environ["SHEET_ID"] = os.environ.get("NEW_BIZ_SHEET_ID", "")
            os.environ["DESTINATIONS"] = os.environ.get("NEW_BIZ_DESTINATIONS", "")

            result = subprocess.run([sys.executable, "new_biz_cat_whatsapp.py"], capture_output=True, text=True)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            
            output = f"STDOUT:\n{result.stdout}\n\nSTDERR:\n{result.stderr}"
            self.wfile.write(output.encode())
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(str(e).encode())
