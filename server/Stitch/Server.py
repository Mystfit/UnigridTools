import http.server
from http import HTTPStatus
import urllib.parse as urlparse
import sys, os, multiprocessing, threading

try:
    from http.server import HTTPServer
except ImportError:
    from BaseHTTPServer import HTTPServer

try:
    import Queue as queue
except ImportError:
    import queue

from Stitch.Stitch import Stitcher


default_port = 8000


class StitchServer(HTTPServer):
    def __init__(self, shared_resource_path, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)
        self.RequestHandlerClass.shared_resource_path = shared_resource_path

class StitchRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args):
        self.stitch_queue = queue.Queue()

        # Start stitcher
        num_threads = max(multiprocessing.cpu_count() - 1, 1)
        self.stitcher = Stitcher(num_threads)

        # Start stitch queue thread
        self.running = True
        t = threading.Thread(target=self.process_stitch_commands, daemon=True)
        t.start()
        http.server.SimpleHTTPRequestHandler.__init__(self, *args)

    def stop_stitcher(self):
        self.running = False

    def process_stitch_commands(self):
        while self.running:
            stitch_args = self.stitch_queue.get(True)
            base_project_path = os.path.join(self.shared_resource_path, "projects", stitch_args['job_id'])
            manifest_path = os.path.join(base_project_path, os.listdir(base_project_path)[0], "manifest.json")
            images_path = os.path.join(self.shared_resource_path, "renders", stitch_args['user'], stitch_args['job_id'])
            self.stitcher.stitch(manifest_path, images_path, images_path)
            print("Stitch for job {} completed".format(stitch_args['job_id']))

    # def do_HEAD(self):
    #     self.send_response(HTTPStatus.OK)
    #     self.end_headers()
    #    # http.server.SimpleHTTPRequestHandler.do_HEAD(self)

    def do_GET(self):
        print("Received path: {}".format(self.path))
        parsed = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed.query)
        print("Received query args: {}".format(query))

        if not 'user' in query or not 'job_id' in query:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        stripped_query = {}
        for key, val in query.items():
            stripped_query[key] = val[0]

        self.stitch_queue.put(stripped_query)
        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def handle_route(self, path):
        pass

def start_server():
    if len(sys.argv) < 2:
        print("Please provide the stitch output path")
        sys.exit()

    shared_resource_path = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else default_port

    httpd = StitchServer(shared_resource_path, ("", port), StitchRequestHandler)
    print("serving at port", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
