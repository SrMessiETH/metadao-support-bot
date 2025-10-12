from http.server import BaseHTTPRequestHandler
import json
import os

BOT_TOKEN = os.environ.get('BOT_TOKEN')

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        """Handle POST requests from Telegram webhook"""
        try:
            print("[v0] POST request received")
            
            # Read request body
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length)
            
            print(f"[v0] Received body: {body.decode('utf-8')}")
            
            # Send success response
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = json.dumps({'ok': True, 'message': 'Received'})
            self.wfile.write(response.encode('utf-8'))
            
            print("[v0] Response sent successfully")
            
        except Exception as e:
            print(f"[v0] Error: {e}")
            import traceback
            traceback.print_exc()
            self.send_response(500)
            self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        print("[v0] GET request received")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Minimal bot is running!')
