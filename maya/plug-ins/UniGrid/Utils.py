import os, shutil, json, subprocess, platform
import urllib2, urllib, httplib

UNIGRID_URL = "https://uni-grid.mddn.vuw.ac.nz"
UNIGRID_LOGIN_URL = UNIGRID_URL + "/login"
UNIGRID_JOBS_URL = UNIGRID_URL + "/jobs"
UNIGRID_NEW_JOB_URL = UNIGRID_JOBS_URL + "/new"
STITCH_URL = "http://grid-dev.mddn.vuw.ac.nz:8000"

# Stitch constants
JOB_UNKNOWN = -1
JOB_IDLE = 1        # Poll
JOB_VALIDATING = 2  # Poll
JOB_RUNNING = 3     # Poll
JOB_COMPLETE = 4    # Poll
JOB_FAILED = 5
STITCH_NOTFOUND = 6 # Poll?
STITCH_RUNNING = 7  # Poll
STITCH_COMPLETE = 8 
STITCH_FAILED = 9

JOB_STATUS_NAME = {
    JOB_UNKNOWN: "Unknown status",
    JOB_VALIDATING: "Render validating",
    JOB_RUNNING: "Render running",
    JOB_COMPLETE: "Render complete",
    JOB_FAILED: "Render failed",
    STITCH_RUNNING: "Stitch running",
    STITCH_COMPLETE: "Stitch complete",
    STITCH_FAILED: "Stitch failed"
}

class ServerException(Exception):
    pass

def get_status_name(status):
    if status:   
        try:
            return JOB_STATUS_NAME[int(status)]
        except KeyError:
            pass
    print("Could not get status name for {}".format(status))
    return JOB_STATUS_NAME[JOB_UNKNOWN]


def get_status_from_name(status_name):
    for status in JOB_STATUS_NAME:
        if status_name == JOB_STATUS_NAME[status]:
            return status
    print("Could not get status name from name {}".format(status))
    return JOB_UNKNOWN


def get_stitch_status(job, url=STITCH_URL):
    status = query_stitch_job(job['id'])
    print("Job {}: Querying stitch status: {}".format(job['id'], status))
    if not status:
        print('No stitch status returned. Returning job status instead')
        return job['status']
    if 'status' in status:
        print('Found stitch job status {}'.format(status['status']))
        if job['status'] >= JOB_COMPLETE:
            print("Job status complete. Returning stitch status {} instead".format(status['status']))
            return status['status']
        else:
            print("Job status not complete. Returning job status {}".format(job['status']))
            return job['status']
    return None


def is_job_pollable(status):
    if (status >= JOB_IDLE and status <= JOB_COMPLETE) or status == STITCH_RUNNING:
        return True
    return False


def cleanup_folder(path):
    for f in os.listdir(path):
        f_path = os.path.join(path, f)
        try:
            if os.path.isfile(f_path):
                os.unlink(f_path)
            elif os.path.isdir(f_path): 
                shutil.rmtree(f_path)
        except Exception as e:
            print(e)


def query_job(job_id, url=UNIGRID_URL):
    job_query_url = "{}/jobs/{}.json".format(url, job_id)
    print("Querying job: {}".format(job_id))
    req = urllib2.Request(job_query_url)
    response = None
    try:
        response = json.loads(urllib2.urlopen(req).read())
    except (urllib2.HTTPError, urllib2.URLError):
        return None

    if 'status' in response:
        if response['status'] == "404":
            print("Job not found")
            return None
    
    return response
    

def query_stitch_job(job_id, url=STITCH_URL):
    # GET request to the stitch server
    stitch_url = "{}/stitch?{}".format(url, urllib.urlencode({'job_id': job_id}))
    request = urllib2.Request(stitch_url)
    print("Querying stitch server for job {}".format(job_id))
    try:
        response = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        # 404 means the job hasn't started stitching
        if e.code == httplib.NOT_FOUND:
            return None
    return json.loads(response.read())


def open_images_folder(job_id, user, passw, *args):
    print("Opening images folder for job {} and user {}".format(job_id, user))
    command = []
    if platform.system() == "Windows":
        server_path = "\\\\uni-grid.mddn.vuw.ac.nz\\uni-grid"
        mount_command = ['net', 'use', '/USER:MDDN\\{}'.format(user), str(server_path), str(passw)]
        subprocess.Popen(mount_command)
        command.append('explorer')
        command.append(os.path.join(server_path, 'renders', str(user), str(job_id), "images"))
    elif platform.system() == "Darwin":
        command.append('open')
        command.append(os.path.join("smb://uni-grid.mddn.vuw.ac.nz/uni-grid/renders", str(user), str(job_id), "images"))
    subprocess.Popen(command)
