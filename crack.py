from http.server import BaseHTTPRequestHandler, HTTPServer
import datetime
BODY = str({
    'messages': [],
    'enterprise_info': {
        'expiration_date': '2099-01-01',
        'expiration_reason': 'paid',
        'enterprise_code': 'abc123',
        'database_already_linked_subscription_url': '',
        'database_already_linked_email': '',
        'database_already_linked_send_mail_url': '',
    },
})

class H(BaseHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] POST request received from {client_ip} -> Path: {self.path}")
        self.send_response(200)
        self.send_header('Content-Type', 'text/plain')
        self.end_headers()
        self.wfile.write(BODY.encode())
    def log_message(self, *a):
        pass

HTTPServer(('127.0.0.1', 8899), H).serve_forever()
