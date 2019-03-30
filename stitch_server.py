import http.server
from http import HTTPStatus
import socketserver
import urllib.parse as urlparse

PORT = 8000

class StitchRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args):
        http.server.SimpleHTTPRequestHandler.__init__(self, *args)

    def do_HEAD(self):
        print("In header for path\n".format(self.path))
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        # http.server.SimpleHTTPRequestHandler.do_HEAD(self)

    def do_GET(self):
        print("In get for path {}\n".format(self.path))
        parsed = urlparse.urlparse(self.path)
        print(urlparse.parse_qs(parsed.query))
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        # http.server.SimpleHTTPRequestHandler.do_GET(self)

    def handle_route(self, path):
        pass

Handler = StitchRequestHandler

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print("serving at port", PORT)
    httpd.serve_forever()
