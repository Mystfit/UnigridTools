from pymel.core import *
from pymel import *
import maya.utils

import os, sys, ssl, platform, threading, urllib2, urllib, time, json, httplib
from functools import partial

import mechanize
from bs4 import BeautifulSoup

import RenderJob
from RenderJob import RenderJobException, MissingAssetException
import AnimRenderJob
from AnimRenderJob import AnimRenderJob
from Singleton import Singleton

# Stitch constants
STITCH_NOTFOUND = 0
STITCH_RUNNING = 1
STITCH_COMPLETE = 4
STITCH_FAILED = 5

STITCH_POLL_TIME = 5.0


@Singleton
class UnigridToolWindow(object):

    def __init__(self):
        self.stitch_server_url = "http://localhost:8000"
        self.pending_stitch_jobs = set()
        self.stitch_watch_thread = threading.Thread(target=self.stitch_poller)
        self.stitch_watch_thread.daemon = True
        self.stitch_watch_thread.start()
        self.create_GUI()

    def create_GUI(self):
        # Window
        print("Creating gui")
        self.win = window(title="Unigrid Export", menuBar=True, width=500)
        self.layout = columnLayout(adjustableColumn=True, rowSpacing=0, columnAlign="left", parent=self.win)
        self.view_menu = menu( label='View')
        self.show_debug_item = menuItem(label="Toggle debug items", command=self.toggle_debug_items)

        job_path_attachments = ["left", "left", "right"]
        frame_bg = (0.286, 0.286, 0.286)
        row_spacing = 4

        # Exported objects
        self.exported_frame = frameLayout(collapse=True, collapsable=True, label="Export settings", marginHeight=2, marginWidth=2, parent=self.layout)
        self.exported_layout = columnLayout(adjustableColumn=True, rowSpacing=row_spacing, columnAlign="left", parent=self.exported_frame)

        # Tiles
        self.tile_frame = frameLayout(collapsable=True, collapse=False, label="Tiles", marginHeight=2, marginWidth=2, parent=self.exported_layout)
        self.tile_layout = columnLayout(adjustableColumn=True, rowSpacing=row_spacing, columnAlign="left", parent=self.tile_frame)
        self.dyn_tiles_toggle = checkBox(label="Dynamic tiles", value=False, visible=False, parent=self.tile_layout)
        
        rowcol_attachments = ["left" for i in range(4)]
        self.row_col_layout = rowLayout(parent=self.tile_layout, numberOfColumns=4, columnAttach4=rowcol_attachments, columnAlign4=rowcol_attachments)
        self.col_text = text(label="Columns", align='center', parent=self.row_col_layout)
        self.cols = intField(value=1, parent=self.row_col_layout, width=100)
        self.row_text = text(label="Rows", align='center', parent=self.row_col_layout)
        self.rows = intField(value=1, parent=self.row_col_layout, width=100)

        # Cameras
        self.camera_layout = rowLayout(parent=self.exported_layout, numberOfColumns=2, columnAttach2=["left", "right"], columnAlign2=["left", "left"], adjustableColumn=1)
        self.camera_list = optionMenu(label="Renderable camera", parent=self.camera_layout)
        self.refresh_cameras()
        self.camera_refresh_button = button(label="Refresh cameras", parent=self.camera_layout)

        # Frames
        frame_attachments = ["left" for i in range(4)]
        self.frames_layout = rowLayout(parent=self.exported_layout, numberOfColumns=4, columnAttach4=frame_attachments, columnAlign4=frame_attachments)
        self.start_frame_text = text(label="Start frame", align='center', parent=self.frames_layout)
        self.start_frame = intField(value=1, parent=self.frames_layout, width=100)
        self.end_frame_text = text(label="End frame", align='center', parent=self.frames_layout)
        self.end_frame = intField(value=1, parent=self.frames_layout, width=100)

        # Static nodes to export
        self.export_selective_toggle = checkBox(label="Export static shapes seperately", changeCommand=self.export_selective_changed, value=False, parent=self.exported_layout)
        self.static_shapes_label = text(label="Static shapes", parent=self.exported_layout)
        self.static_shape_nodes = textScrollList("static_shape_nodes", allowMultiSelection=True, height=100, parent=self.exported_layout)
        self.add_static_shape_btn = button(label="Add static node", parent=self.exported_layout)
        self.remove_static_shape_btn = button(label="Remove static node", parent=self.exported_layout)

        # Dynamic nodes to export
        self.animated_shapes_label = text(label="Per-frame shapes", parent=self.exported_layout)
        self.animated_shape_nodes = textScrollList("animated_shape_nodes", allowMultiSelection=True, height=100, parent=self.exported_layout)
        self.add_anim_shape_btn = button(label="Add animated node", parent=self.exported_layout)
        self.remove_anim_shape_btn = button(label="Remove animated node", parent=self.exported_layout)
        self.export_selective_changed()

        # Server frame        
        self.server_frame = frameLayout(collapsable=True, collapse=False, label="Server", marginHeight=2, marginWidth=2, parent=self.layout)
        self.server_layout = columnLayout(adjustableColumn=True, rowSpacing=row_spacing, columnAlign="left", parent=self.server_frame)
        
        # Login
        login_attachments = ["left" for i in range(6)]
        self.login_frame = frameLayout(collapsable=True, collapse=False, label="Login", marginHeight=2, marginWidth=2, parent=self.server_layout)
        self.login_layout = rowLayout(parent=self.login_frame, numberOfColumns=6, columnAttach6=login_attachments, columnAlign6=login_attachments, adjustableColumn=6)
        self.password = ""
        self.password_field = None

        self.login_label = text(label='Username', align='center', parent=self.login_layout)
        self.login_field = textField(text="", width=100, parent=self.login_layout)
        self.password_label = text(label='Password', align='center', parent=self.login_layout)
        self.password_field = textField(width=100, changeCommand=self.hidePassword, parent=self.login_layout)
        self.email_label = text(label='Email', align='center', parent=self.login_layout)
        self.email_field = textField(text="", width=100, parent=self.login_layout)

        # Upload button
        self.export_upload_btn = button(label="Render", parent=self.layout)

        # Debug frame
        self.debug_frame = frameLayout(collapsable=True, visible=False, label="Debug", marginHeight=2, marginWidth=2, parent=self.layout)
        self.debug_layout = columnLayout(adjustableColumn=True, rowSpacing=row_spacing, columnAlign="left", parent=self.debug_frame)

        self.job_id_layout = rowLayout(parent=self.debug_layout, numberOfColumns=3, columnAttach3=job_path_attachments, columnAlign3=job_path_attachments, adjustableColumn=2)
        self.job_id_label = text(label='Job ID', parent=self.job_id_layout)
        self.job_id_text = textField(text="0000", parent=self.job_id_layout)

        local_stitch_filepath = os.path.normpath(os.path.join(os.path.dirname(__file__), "Stitch.py"))
        self.stitch_remote_layout = rowLayout(parent=self.debug_layout, numberOfColumns=3, columnAttach3=job_path_attachments, columnAlign3=job_path_attachments, adjustableColumn=2)
        self.stitch_url_label = text(label='Remote stitcher URL', parent=self.stitch_remote_layout)
        self.stitch_url = textField(text=self.stitch_server_url, parent=self.stitch_remote_layout)

        self.server_log_label = text(label='Server log', parent=self.debug_layout)
        self.server_logger = textScrollList("grid_log", enable=True, allowMultiSelection=False, height=200, parent=self.debug_layout)

        # Stitch button
        self.stitch_btn = button(label="Stitch tiles", parent=self.debug_layout)

        # Add callbacks to buttons
        # self.export_btn.setCommand(self.exportPressed)
        self.camera_refresh_button.setCommand(self.refresh_cameras)
        self.export_upload_btn.setCommand(self.exportAndUploadPressed)
        self.add_anim_shape_btn.setCommand(self.addAnimPressed)
        self.remove_anim_shape_btn.setCommand(self.removeAnimPressed)
        self.add_static_shape_btn.setCommand(self.addStaticPressed)
        self.remove_static_shape_btn.setCommand(self.removeStaticPressed)
        # self.manifest_path_browse_btn.setCommand(self.setManifestPathPressed)
        # self.tiles_path_browse_btn.setCommand(self.setTilePathPressed)
        self.stitch_btn.setCommand(self.stitch_remote_pressed)

        # Docking panel
        self.docker = dockControl(label="Uni-grid tools", manage=False, content=self.win, area="right")

    def show_GUI(self):
        dockControl(self.docker, edit=True, manage=True)

    def hide_GUI(self):
        dockControl(self.docker, edit=True, manage=False)

    def hidePassword(self, *args):
        self.password = self.password_field.getText()
        self.password_field.setText("*" * len(self.password_field.getText()))

    def export(self):
        print("Exporting...")
        cam = ls(self.camera_list.getValue())[0]
        render_kwargs = {
            'cam': cam,
            'cols': self.cols.getValue(),
            'rows': self.rows.getValue()
        }

        if self.export_selective_toggle.getValue():
            render_kwargs['animated_nodes'] = textScrollList(self.animated_shape_nodes, query=True, allItems=True)
            render_kwargs['static_nodes'] = textScrollList(self.static_shape_nodes, query=True, allItems=True)

        if self.dyn_tiles_toggle.getValue():
            render_kwargs['dynamic_tiles'] = True

        renderjob = AnimRenderJob(self.start_frame.getValue(), self.end_frame.getValue(), **render_kwargs)
        
        try:
            renderjob.export()
            return renderjob
        except RenderJobException as e:
            confirmDialog(title="Uni-grid Error", message=str(e))
        except MissingAssetException as e:
            self.missing_assets_dialog(e.missing_assets)

        return None

    def upload(self, job):
        # URLs
        unigrid_url = 'https://uni-grid.mddn.vuw.ac.nz'
        unigrid_login_url = unigrid_url + "/login"
        unigrid_jobs_url = unigrid_url + "/jobs"
        unigrid_new_job_url = unigrid_jobs_url + "/new"

        # Set up mechanize
        ssl._create_default_https_context = ssl._create_unverified_context
        br = mechanize.Browser()
        br.set_handle_robots(False) # ignore robots

        # Get login page
        br.open(unigrid_login_url)
        form = br.select_form(nr=0)
        br.set_all_readonly(False)

        # Set login values
        user = self.login_field.getText()
        if user and self.password:
            br.set_value(self.login_field.getText(), name="user[short_name]")
            br.set_value(self.password, name="user[password]")
            res = None
            try:
                res = br.submit()
            except urllib2.HTTPError as e:
                fail_msg = "Uni-grid login failed. Server response: {}".format(e)
                confirmDialog(title="Uni-grid", message=fail_msg)
                self.server_log(fail_msg)
                return

            # Check login success
            if res.geturl() == unigrid_login_url:
                self.server_log("Login failed")
                confirmDialog(title="Uni-grid", message="Uni-grid login rejected. Check your username and password.")
                return        
            self.server_log("Login successful")
        else:
            self.server_log("No login info provided. Rendering as guest")

        # Get new job page
        br.open(unigrid_new_job_url)
        br.select_form(id="new_job")
        br["job[job_type]"] = ["Arnold"]

        # Set job variables
        br.set_value(self.email_field.getText(), name="job[email]")
        br.set_value(os.path.basename(system.sceneName()), name="job[scene]")
        br.set_value(str(self.start_frame.getValue()), name="job[start_frame]")
        br.set_value(str(self.cols.getValue() * self.rows.getValue() * ((self.end_frame.getValue() - self.start_frame.getValue() + 1))), name="job[end_frame]")
        br.form.add_file(open(job.zip_path, 'rb'), 'application/zip', job.zip_path, name="job[project_zip]")
        res = br.submit()

        # Check job submission success
        job_id = None
        if res.geturl() == unigrid_jobs_url:
            soup = BeautifulSoup(res.read())
            error_str = ""
            for error in soup.find('div', id="error_explanation").find_all('li'):
                error_str += "- {}\n".format(error.string)
            errors = [error.string + "\n" ]
            self.server_log("Server rejected the render job.\n\n{}".format(error_str))
            confirmDialog(title="Uni-grid error", message="Server rejected the render job.\n\n{}".format(error_str))
            return
        
        # Get new job ID from the returned URL
        job.job_id = res.geturl().split("/")[-1]
        self.job_id_text.setText(job.job_id)

        self.stitch_remote(job.job_id)

        confirmDialog(title="Uni-grid", message="Render submitted successfully.\n\nJob ID: {}".format(job.job_id))

    def stitch_poller(self):
        while True:
            removed_stitch_jobs = set()
            for job_id in self.pending_stitch_jobs:
                status = self.get_stitch_status(job_id)
                maya.utils.executeInMainThreadWithResult(self.server_log, "Job {} status: {}".format(job_id, status))
                if status:
                    if status['status'] == STITCH_COMPLETE:
                        removed_stitch_jobs.add(job_id)
                        maya.utils.executeInMainThreadWithResult(self.stitch_complete, "Stitch for job {} complete".format(job_id))
                    elif status['status'] == STITCH_FAILED:
                        removed_stitch_jobs.add(job_id)

            for job_id in removed_stitch_jobs:
                self.pending_stitch_jobs.remove(job_id)

            time.sleep(STITCH_POLL_TIME)

    def stitch_remote(self, job_id):
        self.server_log("Submitting stitch job to {}".format(self.stitch_url.getText()))
        
        # POST request to the stitch server letting it know to watch for a completed Uni-grid job
        args = urllib.urlencode({'job_id': job_id})
        request = urllib2.Request("{}/stitch".format(self.stitch_url.getText()), args)
        response = urllib2.urlopen(request)
        self.pending_stitch_jobs.add(job_id)
        self.server_log("Stitch server respose code: {}".format(response.getcode()))

    def get_stitch_status(self, job_id):       
        # GET request to the stitch server
        stitch_url = "{}/stitch?{}".format(self.stitch_url.getText(), urllib.urlencode({'job_id': job_id}))
        request = urllib2.Request(stitch_url)
        
        try:
            response = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            # 404 means the job hasn't started stitching
            if e.code == httplib.NOT_FOUND:
                return None
        return json.loads(response.read())

    def refresh_cameras(self, *args):
        optionMenu(self.camera_list, edit=True, deleteAllItems=True)
        self.camera_list.addItems([cam.name() for cam in ls(cameras=True) if cam.renderable.get()])

    # Callback functions
    def toggle_debug_items(self, *args):
        frameLayout(self.debug_frame, edit=True, visible=not frameLayout(self.debug_frame, query=True, visible=True))

    def exportPressed(self, *args):
        job = self.export()
        confirmDialog(title="Uni-grid", message="Manifest and zip located at\n{}".format(job.manifest_filepath))

    def exportAndUploadPressed(self, *args):
        job = self.export()
        if job:
            self.upload(job)

    def export_selective_changed(self, *args):
        enabled = self.export_selective_toggle.getValue()

        text(self.static_shapes_label, edit=True, enable=enabled, visible=enabled)
        textScrollList(self.static_shape_nodes, edit=True, enable=enabled, visible=enabled)
        button(self.add_static_shape_btn, edit=True, enable=enabled, visible=enabled)
        button(self.remove_static_shape_btn, edit=True, enable=enabled, visible=enabled)

        text(self.animated_shapes_label, edit=True, enable=enabled, visible=enabled)
        textScrollList(self.animated_shape_nodes, edit=True, enable=enabled, visible=enabled)
        button(self.add_anim_shape_btn, edit=True, enable=enabled, visible=enabled)
        button(self.remove_anim_shape_btn, edit=True, enable=enabled, visible=enabled)

    def addAnimPressed(self, *args):
        for node in listRelatives(ls(selection=True), shapes=True):
            static_and_animated_items = textScrollList(self.animated_shape_nodes, query=True, allItems=True) + textScrollList(self.static_shape_nodes, query=True, allItems=True)
            if node.name() not in static_and_animated_items:
                self.animated_shape_nodes.append(node.name())

    def addStaticPressed(self, *args):
        for node in listRelatives(ls(selection=True), shapes=True):
            static_and_animated_items = textScrollList(self.animated_shape_nodes, query=True, allItems=True) + textScrollList(self.static_shape_nodes, query=True, allItems=True)
            if node.name() not in static_and_animated_items:
                self.static_shape_nodes.append(node.name())

    def removeAnimPressed(self, *args):
        for node in textScrollList(self.animated_shape_nodes, query=True, si=True):
            self.animated_shape_nodes.removeItem(node)

    def removeStaticPressed(self, *args):
        for node in textScrollList(self.static_shape_nodes, query=True, si=True):
            self.static_shape_nodes.removeItem(node)

    def setManifestPathPressed(self, *args):
        self.manifest_path.setText(promptForFolder())

    def setTilePathPressed(self, *args):
        self.tiles_path.setText(promptForFolder())

    def stitch_remote_pressed(self, *args):
        self.stitch_remote(self.job_id_text.getText().rstrip())

    def stitch_complete(self, returnmessage):
        confirmDialog(title="Uni-grid", message=returnmessage)

    def missing_assets_dialog(self, missing_asset_nodes):
        missing_assets_win = window(title="Uni-grid export error", width=500, height=220)
        missing_assets_win.show()

        layout = columnLayout(adjustableColumn=True, height=200, rowSpacing=row_spacing, columnAlign="left", parent=missing_assets_win)
        text(label='The following nodes have missing external dependencies. Check your paths!\nClick to select', align="left", parent=layout)
        missing_asset_list = textScrollList("missing_texture_list", height=200, parent=layout) 
        textScrollList(missing_asset_list, edit=True, sc=partial(goto_missing_asset, missing_asset_list))
        for asset in missing_asset_nodes:
            missing_asset_list.append(asset.name())

    def server_log(self, message):
        self.server_logger.append(message)


def goto_missing_asset(scrollList):
    node = textScrollList(scrollList, query=True, si=True)
    if node:
        print("Missing asset node: {}".format(node[0]))
        select(node[0])
    return ""

