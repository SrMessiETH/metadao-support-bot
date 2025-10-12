from http.server import BaseHTTPRequestHandler
import json
import sys
import traceback

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # Try importing telegram libraries
            import telegram
            from telegram import Update
            from telegram.ext import Application
            
            response = {
                "status": "success",
                "telegram_version": telegram.__version__,
                "message": "All imports successful"
            }
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            error_response = {
                "status": "error",
                "error": str(e),
                "traceback": traceback.format_exc()
            }
            
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(error_response).encode())
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b"Import test endpoint")
