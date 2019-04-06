import http.server
from http import HTTPStatus
import urllib
from pathlib import Path
import urllib.parse as urlparse
from urllib import request
import sys, os, multiprocessing, threading, json, time, ssl
from json import JSONEncoder

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

STITCH_NOTFOUND = 6
STITCH_RUNNING = 7
STITCH_COMPLETE = 8
STITCH_FAILED = 9

ssl._create_default_https_context = ssl._create_unverified_context


class StitchJob(object):
    def __init__(self, job_id, user, shared_resource_path):
        self.job_id = job_id
        self.user = user
        self.status = STITCH_RUNNING
        self.frames = []

        base_project = os.path.join(shared_resource_path, "projects", job_id)
        self.project_path = os.path.join(base_project, os.listdir(base_project)[0])
        self.image_path = os.path.join(shared_resource_path, "renders", user, job_id)
        with open(os.path.join(self.project_path, "manifest.json"), 'r') as f:
            self.manifest = json.loads(f.read())

    def fail(self):
        self.status = STITCH_FAILED

    def complete(self):
        for file in self.manifest['frames']:
            path = Path(os.path.join(self.image_path, file['outfile']))
            self.frames.append(str(path))

        print("Stitch job {} completed".format(self.job_id))
        self.status = STITCH_COMPLETE

    def toJSON(self):
        data = {
            'job_id': self.job_id, 
            'user': self.user,
            'status': self.status,
            'frames': self.frames
        }
        return json.dumps(data)


class StitchEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, StitchJob):
            return {
                'job_id': o.job_id, 
                'user': o.user,
                'status': o.status,
                'frames': o.frames
            }
        return super().default(self, o)


class StitchServer(HTTPServer):
    def __init__(self, shared_resource_path, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)

        self.stitch_queue = queue.Queue()
        self.watchlist = set()
        self.jobs = {}

        # Start stitcher
        num_threads = max(multiprocessing.cpu_count() - 1, 1)
        self.stitcher = Stitcher(num_threads)

        # Start stitch queue thread
        self.running = True
        self.stitch_command_thread = threading.Thread(target=self.process_stitch_commands, daemon=True)
        self.stitch_command_thread.start()

        self.watch_job_thread = threading.Thread(target=self.poll_jobs, daemon=True)
        self.watch_job_thread.start()

        self.shared_resource_path = shared_resource_path

    def stop_stitcher(self):
        self.running = False

    def process_stitch_commands(self):
        while self.running:
            stitch_job = self.stitch_queue.get(True)
            self.stitcher.stitch(os.path.join(stitch_job.project_path, "manifest.json"), stitch_job.image_path, stitch_job.image_path)
            stitch_job.complete()

    def poll_jobs(self):
        while self.running:
            removed_jobs = set()
            for job_id in self.watchlist:
                job_args = self.query_job(job_id)
                if not job_args:
                    removed_jobs.add(job_id)
                    continue

                print("Watching job {}".format(job_id))

                # Query completed and failed jobs to see if we can perform a stitch
                if job_args['status'] == JOB_COMPLETE:
                    print("Job {} finished rendering. Queueing stitch".format(job_id))
                    job = StitchJob(job_id, job_args['short_name'], self.shared_resource_path)
                    self.jobs[job_id] = job
                    self.stitch_queue.put(job)
                    removed_jobs.add(job_id)
                elif job_args['status'] == JOB_FAILED:
                    print("Job {} failed. Removing".format(job_id))
                    removed_jobs.add(job_id)

            # Prune jobs after we finish iterating over the set
            for job_id in removed_jobs:
                self.remove_watched_job(job_id)

            time.sleep(UNIGRID_POLL_TIME)

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
        try:
            response = request.urlopen(req)
        except urllib.error.HTTPError:
            return None
        
        response_data = json.loads(response.read())
        if 'status' in response_data:
            if response_data['status'] == "404":
                print("Job not found")
                return None
        return response_data


class StitchRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, request, client_address, server):
        self.server = server
        http.server.SimpleHTTPRequestHandler.__init__(self,  request, client_address, server)

    def do_POST(self):
        parsed = urlparse.urlparse(self.path)
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        query = urlparse.parse_qs(body)
        reply = (HTTPStatus.NOT_IMPLEMENTED,)

        if parsed.path.startswith("/stitch"):
            reply = self.handle_stitch_post(self.strip_args(query))
        else:
            reply = (HTTPStatus.NOT_FOUND)

        self.send_response(reply[0])
        self.end_headers()

        if len(reply) > 1:
            self.wfile.write(reply[1])

    def do_GET(self):
        parsed = urlparse.urlparse(self.path)
        query = urlparse.parse_qs(parsed.query)
        reply = (HTTPStatus.NOT_IMPLEMENTED,)

        if parsed.path.startswith("/stitch"):
            reply = self.handle_stitch_get(self.strip_args(query))
        else:
            reply = (HTTPStatus.NOT_FOUND,)

        self.send_response(reply[0])
        self.send_header('Content-type', 'application/json')    
        self.end_headers()
        if len(reply) > 1:
            self.wfile.write(reply[1])

    def strip_args(self, args):
        stripped_args = {}
        for key, val in args.items():
            if isinstance(key, bytes):
                stripped_args[key.decode("utf-8")] = val[0].decode("utf-8") 
            else:
                stripped_args[key] = val[0]

        return stripped_args

    def handle_stitch_post(self, args):
        if not 'job_id' in args:
            return (HTTPStatus.BAD_REQUEST,)

        self.server.watch_job(args['job_id'])
        return (HTTPStatus.OK,)

    def handle_stitch_get(self, args):
        if 'job_id' in args:
            if args['job_id'] in self.server.jobs:
                return (HTTPStatus.OK, str.encode(self.server.jobs[args['job_id']].toJSON()))

        return (HTTPStatus.OK, str.encode(json.dumps(self.server.jobs, cls=StitchJobEncoder)))


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
