import http.server
from http import HTTPStatus
import urllib
import urllib.parse as urlparse
from urllib import request
import sys, os, multiprocessing, threading, json, time, ssl

try:
    from http.server import HTTPServer
except ImportError:
    from BaseHTTPServer import HTTPServer

try:
    import Queue as queue
except ImportError:
    import queue

from Stitch.Stitch import Stitcher


DEFAULT_PORT = 8000
UNIGRID_URL = "https://uni-grid.mddn.vuw.ac.nz"
UNIGRID_POLL_TIME = 5

JOB_COMPLETE = 4
JOB_FAILED = 5

ssl._create_default_https_context = ssl._create_unverified_context


class StitchServer(HTTPServer):
    def __init__(self, shared_resource_path, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)
        self.RequestHandlerClass.shared_resource_path = shared_resource_path

class StitchRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args):
        self.stitch_queue = queue.Queue()
        self.watchlist = set()

        # Start stitcher
        num_threads = max(multiprocessing.cpu_count() - 1, 1)
        self.stitcher = Stitcher(num_threads)

        # Start stitch queue thread
        self.running = True
        self.stitch_command_thread = threading.Thread(target=self.process_stitch_commands, daemon=True)
        self.stitch_command_thread.start()

        self.watch_job_thread = threading.Thread(target=self.watch_jobs, daemon=True)
        self.watch_job_thread.start()

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

    def watch_jobs(self):
        while self.running:
            removed_jobs = set()
            for job_id in self.watchlist:
                job_args = self.query_job(job_id)
                if not job_args:
                    self.remove_watched_job(job_id)
                    continue

                # Query completed and failed jobs to see if we can perform a stitch
                if job_args['status'] == JOB_COMPLETE:
                    print("Watched job {} completed. Queueing stitch".format(job_id))
                    self.stitch_queue.put({'job_id':job_id, 'user': job_args['short_name']})
                    removed_jobs.add(job_id)
                elif job_args['status'] == JOB_FAILED:
                    print("Watched job {} failed. Removing".format(job_id))
                    removed_jobs.add(job_id)

            # Prune jobs after we finish iterating over the set
            for job_id in removed_jobs:
                self.remove_watched_job(job_id)


            time.sleep(UNIGRID_POLL_TIME)

    def do_GET(self):
        print("Received path: {}".format(self.path))
        parsed = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed.query)

        if not 'job_id' in query:
            self.send_response(HTTPStatus.BAD_REQUEST)
            self.end_headers()
            return

        stripped_query = {}
        for key, val in query.items():
            stripped_query[key] = val[0]

        print("Received query args: {}".format(stripped_query))
        self.watch_job(stripped_query['job_id'])

        self.send_response(HTTPStatus.OK)
        self.end_headers()

    def watch_job(self, job_id):
        if not job_id in self.watchlist:
            job = self.query_job(job_id)
            if not job:
                return
            self.watchlist.add(job_id)

    def remove_watched_job(self, job_id):
        try: 
            self.watchlist.remove(job_id)
        except KeyError: 
            pass 

    def query_job(self, job_id):
        job_query_url = "{}/jobs/{}.json".format(UNIGRID_URL, job_id)
        print("Querying job: {}".format(job_id))
        req = request.Request(job_query_url)
        response = json.loads(request.urlopen(req).read())
        if 'status' in response:
            if response['status'] == "404":
                print("Job not found")
                return None
        return response


def start_server():
    if len(sys.argv) < 2:
        print("Please provide the stitch output path")
        sys.exit()

    shared_resource_path = sys.argv[1]
    port = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_PORT

    httpd = StitchServer(shared_resource_path, ("", port), StitchRequestHandler)
    print("serving at port", port)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
