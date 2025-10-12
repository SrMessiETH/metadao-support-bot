from http.server import BaseHTTPRequestHandler
import json

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read content length
        content_length = int(self.headers.get('Content-Length', 0))
        
        # Read the body
        body = self.rfile.read(content_length)
        
        # Send response
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        response = {
            'ok': True,
            'message': 'POST received',
            'body_length': content_length
        }
        
        self.wfile.write(json.dumps(response).encode('utf-8'))
        return
    
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'Test endpoint is working!')
        return
