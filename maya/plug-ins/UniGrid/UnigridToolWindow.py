from pymel.core import *
from pymel import *
import maya.utils

import os, sys, ssl, platform, threading, urllib2, urllib, time, json, httplib, subprocess
from functools import partial

import mechanize
from bs4 import BeautifulSoup

import RenderJob
from RenderJob import RenderJobException, MissingAssetException
import AnimRenderJob
from AnimRenderJob import AnimRenderJob
from Singleton import Singleton
import Utils


STITCH_POLL_TIME = 20.0

@Singleton
class UnigridToolWindow(object):

    def __init__(self):
        ssl._create_default_https_context = ssl._create_unverified_context

        self.stitch_server_url = Utils.STITCH_URL
        self.ran_jobs = []

        # Set up mechanize
        self.active_login = None
        self.br = mechanize.Browser()
        self.br.set_handle_robots(False) # ignore robots
        self.br.set_handle_refresh(False)

        # Create GUI
        self.create_GUI()

        # Start threads
        self.poll_running = True
        self.stitch_watch_thread = threading.Thread(target=self.stitch_poller)
        self.stitch_watch_thread.daemon = True
        self.stitch_watch_thread.start()

        # Load jobs from disk
        self.load_saved_jobs(os.path.basename(system.sceneName()))

    def create_GUI(self):
        # Window
        print("Creating gui")
        win = window(title="Unigrid Export", menuBar=True, width=500)

        scroll_layout = scrollLayout(childResizable=True, verticalScrollBarThickness=16, parent=win)
        main_layout = columnLayout(adjustableColumn=True, rowSpacing=0, columnAlign="left", parent=scroll_layout)
        view_menu = menu( label='View')
        show_debug_item = menuItem(label="Toggle debug items", command=self.toggle_debug_items)

        job_path_attachments = ["left", "left", "right"]
        frame_bg = (0.286, 0.286, 0.286)
        self.row_spacing = 4

        # Exported objects
        exported_frame = frameLayout(collapse=True, collapsable=True, label="Export settings", marginHeight=2, marginWidth=2, parent=main_layout)
        exported_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=exported_frame)

        # Tiles
        tile_frame = frameLayout(collapsable=True, collapse=False, label="Tiles", marginHeight=2, marginWidth=2, parent=exported_layout)
        tile_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=tile_frame)
        self.dyn_tiles_toggle = checkBox(label="Dynamic tiles", value=False, visible=False, parent=tile_layout)
        rowcol_attachments = ["left" for i in range(4)]
        row_col_layout = rowLayout(parent=tile_layout, numberOfColumns=4, columnAttach4=rowcol_attachments, columnAlign4=rowcol_attachments)
        col_text = text(label="Columns", align='center', parent=row_col_layout)
        self.cols = intField(value=1, parent=row_col_layout, width=100)
        row_text = text(label="Rows", align='center', parent=row_col_layout)
        self.rows = intField(value=1, parent=row_col_layout, width=100)

        # Cameras
        camera_layout = rowLayout(parent=exported_layout, numberOfColumns=2, columnAttach2=["left", "right"], columnAlign2=["left", "left"], adjustableColumn=1)
        self.camera_list = optionMenu(label="Renderable camera", parent=camera_layout)
        self.refresh_cameras()
        camera_refresh_button = button(label="Refresh cameras", parent=camera_layout, command=self.refresh_cameras)

        # Frames
        frame_attachments = ["left" for i in range(4)]
        frames_layout = rowLayout(parent=exported_layout, numberOfColumns=4, columnAttach4=frame_attachments, columnAlign4=frame_attachments)
        start_frame_text = text(label="Start frame", align='center', parent=frames_layout)
        self.start_frame = intField(value=1, parent=frames_layout, width=100)
        end_frame_text = text(label="End frame", align='center', parent=frames_layout)
        self.end_frame = intField(value=1, parent=frames_layout, width=100)

        # Static nodes to export
        self.export_selective_toggle = checkBox(label="Export static shapes seperately", changeCommand=self.export_selective_changed, value=False, parent=exported_layout)
        self.export_selective_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=exported_layout)
        static_shapes_label = text(label="Static shapes", parent=self.export_selective_layout)
        self.static_shape_nodes = textScrollList("static_shape_nodes", allowMultiSelection=True, height=100, parent=self.export_selective_layout)
        add_static_shape_btn = button(label="Add static node", command=self.addStaticPressed, parent=self.export_selective_layout)
        remove_static_shape_btn = button(label="Remove static node", command=self.removeStaticPressed, parent=self.export_selective_layout)

        # Dynamic nodes to export
        animated_shapes_label = text(label="Per-frame shapes", parent=self.export_selective_layout)
        self.animated_shape_nodes = textScrollList("animated_shape_nodes", allowMultiSelection=True, height=100, parent=self.export_selective_layout)
        add_anim_shape_btn = button(label="Add animated node", command=self.addAnimPressed, parent=self.export_selective_layout)
        remove_anim_shape_btn = button(label="Remove animated node", command=self.removeAnimPressed, parent=self.export_selective_layout)
        self.export_selective_changed()

        # Server frame        
        server_frame = frameLayout(collapsable=True, collapse=False, label="Server", marginHeight=2, marginWidth=2, parent=main_layout)
        server_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=server_frame)
        
        # Login
        login_attachments = ["left" for i in range(6)]
        login_frame = frameLayout(collapsable=True, collapse=False, label="Login", marginHeight=2, marginWidth=2, parent=server_layout)
        login_layout = rowLayout(parent=login_frame, numberOfColumns=6, columnAttach6=login_attachments, columnAlign6=login_attachments, adjustableColumn=6)
        self.password = ""

        login_label = text(label='Username', align='center', parent=login_layout)
        self.login_field = textField(text="", width=100, parent=login_layout)
        password_label = text(label='Password', align='center', parent=login_layout)
        self.password_field = textField(width=100, changeCommand=self.hidePassword, parent=login_layout)
        email_label = text(label='Email', align='center', parent=login_layout)
        self.email_field = textField(text="", width=100, parent=login_layout)

        # Existing jobs
        job_frame = frameLayout(collapsable=True, collapse=False, label="Scene jobs", marginHeight=2, marginWidth=2, parent=server_layout)
        job_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=job_frame)
        jobs_refresh = button(label='Refresh', command=self.refresh_pressed, parent=job_layout)
        
        self.job_scroll_min_height = 75
        self.job_scroll_max_height = 300
        self.job_scroll_layout = scrollLayout(childResizable=True, verticalScrollBarThickness=16, height=self.job_scroll_min_height, resizeCommand=self.resize_job_table, parent=job_layout)
        self.job_details_col_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=self.job_scroll_layout)

        job_header_align = ["left" for i in range(4)]
        self.job_details_col_spacing = [50, 70, 100, 80]
        self.job_details_row_header_layout = rowLayout(parent=self.job_details_col_layout, numberOfColumns=4, columnAttach4=job_header_align, columnAlign4=job_header_align)
        job_detail_id_text = text(label='Job ID', font='boldLabelFont', align='left', width=self.job_details_col_spacing[0], parent=self.job_details_row_header_layout)
        job_detail_user_text = text(label='User', font='boldLabelFont', align='left', width=self.job_details_col_spacing[1], parent=self.job_details_row_header_layout)
        job_detail_status_text = text(label='Status', font='boldLabelFont', align='left', width=self.job_details_col_spacing[2], parent=self.job_details_row_header_layout)
        job_detail_command_text = text(label='Commands', font='boldLabelFont', align='left', width=self.job_details_col_spacing[3], parent=self.job_details_row_header_layout)
        
        separator(height=20, parent=main_layout)

        # Upload button
        export_upload_btn = button(label="Render", parent=main_layout, command=self.exportAndUploadPressed)

        # Debug frame
        self.debug_frame = frameLayout(collapsable=True, visible=False, label="Debug", marginHeight=2, marginWidth=2, parent=main_layout)
        debug_layout = columnLayout(adjustableColumn=True, rowSpacing=self.row_spacing, columnAlign="left", parent=self.debug_frame)

        job_id_layout = rowLayout(parent=debug_layout, numberOfColumns=3, columnAttach3=job_path_attachments, columnAlign3=job_path_attachments, adjustableColumn=2)
        job_id_label = text(label='Job ID', parent=job_id_layout)
        self.job_id_text = textField(text="0000", parent=job_id_layout)

        local_stitch_filepath = os.path.normpath(os.path.join(os.path.dirname(__file__), "Stitch.py"))
        stitch_remote_layout = rowLayout(parent=debug_layout, numberOfColumns=3, columnAttach3=job_path_attachments, columnAlign3=job_path_attachments, adjustableColumn=2)
        stitch_url_label = text(label='Remote stitcher URL', parent=stitch_remote_layout)
        self.stitch_url = textField(text=self.stitch_server_url, parent=stitch_remote_layout)

        server_log_label = text(label='Server log', parent=debug_layout)
        self.server_logger = textScrollList("grid_log", enable=True, allowMultiSelection=False, height=200, parent=debug_layout)
        
        stitch_btn = button(label="Stitch tiles", command=self.stitch_remote_pressed, parent=debug_layout)

        self.docker = dockControl(label="Uni-grid tools", manage=False, content=win, area="right")

    def show_GUI(self):
        dockControl(self.docker, edit=True, manage=True)

    def hide_GUI(self):
        dockControl(self.docker, edit=True, manage=False)

    def hidePassword(self, *args):
        self.password = self.password_field.getText()
        self.password_field.setText("*" * len(self.password_field.getText()))

    def unigrid_data_dir(self):
        path = os.path.normpath(os.path.join(workspace.getPath(), 'data', 'unigrid'))
        try:
            os.makedirs(path)
        except OSError as e:
            pass
        return path

    def clear_jobs_list(self):
        children = columnLayout(self.job_details_col_layout, query=True, childArray=True)
        for row in range(1, len(children)):
            deleteUI(row, control=True)

    def add_job_detail_row(self, job_id, user):
        job_detail_align = ["left" for i in range(6)]
        row = rowLayout(parent=self.job_details_col_layout, numberOfColumns=6, columnAttach6=job_detail_align, columnAlign6=job_detail_align),
        text(label=job_id, font='plainLabelFont', align='left', width=self.job_details_col_spacing[0])
        text(label=user, font='plainLabelFont', align='left', width=self.job_details_col_spacing[1])
        text(label="", font='plainLabelFont', align='left', width=self.job_details_col_spacing[2])
        button(label='Open images folder', command=partial(self.open_images_folder_pressed, job_id, user))
        button(label='Show image path', command=partial(self.show_image_folder, job_id, user))
        button(label='Delete job', command=partial(self.delete_job, job_id))
        self.resize_job_table(self)
        return rowLayout(row, query=True, childArray=True)

    def update_job_detail_row(self, row, job_id, user, status):
        text(row[0], edit=True, label=job_id)
        text(row[1], edit=True, label=user)
        text(row[2], edit=True, label=Utils.get_status_name(status))

    def get_job_row(self, job_id):
        col_children = columnLayout(self.job_details_col_layout, query=True, childArray=True)
        for col_i in range(1, len(col_children)):
            row = col_children[col_i]
            row_children = rowLayout(col_children[col_i], query=True, childArray=True)
            row_job_id = text(row_children[0], query=True, label=True)
            if str(row_job_id) == str(job_id):
                return row
        return None

    def remove_job_detail_row(self, job_id):
        try:
            self.ran_jobs.remove(job_id)
        except ValueError:
            pass
        maya.utils.executeInMainThreadWithResult(self.delete_row, self.get_job_row(job_id))

    def lock_job_detail_row(self, job_id):
        row = self.get_job_row(job_id)
        rowLayout(row, edit=True, enable=False)

    def unlock_job_detail_row(self, job_id):
        row = self.get_job_row(job_id)
        rowLayout(row, edit=True, enable=True)

    def resize_job_table(self, *args):
        rows = columnLayout(self.job_details_col_layout, query=True, childArray=True)
        margin = 20
        total_height = margin
        for row in rows:
            total_height += rowLayout(row, query=True, height=True)
        scrollLayout(self.job_scroll_layout, edit=True, height=min(total_height, self.job_scroll_max_height))

    def delete_row(self, row):
        deleteUI(row, control=True)

    def store_job(self, job_id, scene_name):
        self.ran_jobs.append(job_id)
        job = Utils.query_job(job_id)
        self.update_job_detail_row(self.add_job_detail_row(job['id'], job['short_name']), job['id'], job['short_name'], Utils.get_stitch_status(job))
        self.save_jobs(scene_name)
        
    def open_images_folder_pressed(self, job_id, user, *args):
        pword = self.password
        if not pword:
            result = promptDialog(
                    title='Uni-grid Login',
                    message='Enter the password for user {}:'.format(user),
                    button=['OK', 'Cancel'],
                    defaultButton='OK',
                    cancelButton='Cancel',
                    dismissString='Cancel')
            if result == 'OK':
                pword = promptDialog(query=True, text=True)
            else:
                return
        
        Utils.open_images_folder(job_id, user, pword)

    def show_image_folder(self, job_id, user, *args):
        msg = os.path.join("\\\\uni-grid.mddn.vuw.ac.nz\\uni-grid\\renders", str(user), str(job_id), "images")
        print(msg)
        confirmDialog(title="Uni-grid", message=msg)

    def delete_job(self, job_id, *args):
        # Freeze UI controls
        self.lock_job_detail_row(job_id)

        # Login
        try:
            self.login(self.login_field.getText(), self.password)
        except Utils.ServerException as e:
            confirmDialog(title="Uni-grid error", message=e)
            return
        
        # Login page sends us to job page by default
        response_data = self.br.response().read()
        soup = BeautifulSoup(response_data, features="html5lib")

        # Get CSRF token
        auth_token_tag = soup.find('meta', attrs={"name": "csrf-token"})
        auth_token = auth_token_tag['content']
        args = urllib.urlencode({
            '_method': 'delete',
            'authenticity_token': auth_token
        })

        # Delete job
        try:
            delete_response = self.br.open("{}/{}".format(Utils.UNIGRID_JOBS_URL, job_id), args)
            delete_response_data = delete_response.read()
            soup = BeautifulSoup(delete_response_data, features="html5lib")
            notice = soup.find('p', id='notice').string
            self.server_log("Delete request - Server responded: {}".format(notice))
        except urllib2.HTTPError as e:
            if e.code == httplib.NOT_FOUND:
                pass

        # Remove job items
        self.remove_job_detail_row(job_id)


    def load_saved_jobs(self, scene_name):
        file = None
        try:
            with open(os.path.join(self.unigrid_data_dir(), '{}.json'.format(scene_name)), 'r') as f:
                data = f.read()
                if data:
                    self.ran_jobs = json.loads(data)
        except IOError:
            pass

        self.clear_jobs_list()
        pruned_jobs = []
        for job_id in self.ran_jobs:
            job = Utils.query_job(job_id)
            if not job:
                pruned_jobs.append(job_id)
                continue
            self.update_job_detail_row(self.add_job_detail_row(job['id'], job['short_name']), job['id'], job['short_name'], Utils.get_stitch_status(job))
        for job_id in pruned_jobs:
            try:
                self.ran_jobs.remove(job_id)
            except RuntimeError:
                pass

        # Remove missing jobs from disk
        self.save_jobs(scene_name)

    def save_jobs(self, scene_name):
        with open(os.path.join(self.unigrid_data_dir(), scene_name) + ".json", "w+") as f:
            f.write(json.dumps(self.ran_jobs))

    def update_jobs(self, force=False):
        col_children = columnLayout(self.job_details_col_layout, query=True, childArray=True)
        if not col_children:
            return

        # Iterate over rows, skip header
        for col_i in range(1, len(col_children)):
            row = rowLayout(col_children[col_i], query=True, childArray=True)
            if not row:
                continue
            row_job_id = text(row[0], query=True, label=True)
            row_job_user = text(row[1], query=True, label=True)
            row_job_status = Utils.JOB_UNKNOWN
            row_job_status_text = text(row[2], query=True, label=True)
            if not row_job_status_text:
                row_job_status = Utils.get_status_from_name(Utils.get_status_name(Utils.JOB_UNKNOWN))
            else:
                row_job_status = Utils.get_status_from_name(row_job_status_text)

            if row_job_id in self.ran_jobs and (Utils.is_job_pollable(row_job_status) or force): 
                # Query job status from Unigrid
                job = Utils.query_job(row_job_id)
                if not job:
                    self.remove_job_detail_row(row_job_id)
                    continue

                self.update_job_detail_row(row, row_job_id, job['short_name'], Utils.get_stitch_status(job))

    def export(self):
        print("Exporting...")
        cam = ls(self.camera_list.getValue())[0]
        render_kwargs = {
            'cam': cam,
            'cols': self.cols.getValue(),
            'rows': self.rows.getValue()
        }

        # Export selective lists
        if self.export_selective_toggle.getValue():
            render_kwargs['animated_nodes'] = textScrollList(self.animated_shape_nodes, query=True, allItems=True)
            render_kwargs['static_nodes'] = textScrollList(self.static_shape_nodes, query=True, allItems=True)

        # Generate dynamic tiles
        if self.dyn_tiles_toggle.getValue():
            render_kwargs['dynamic_tiles'] = True

        # Create render job
        renderjob = AnimRenderJob(self.start_frame.getValue(), self.end_frame.getValue(), **render_kwargs)
        
        try:
            renderjob.export()
            return renderjob
        except RenderJobException as e:
            confirmDialog(title="Uni-grid Error", message=str(e))
        except MissingAssetException as e:
            self.missing_assets_dialog(e.missing_assets)

        return None

    def login(self, user, passw):
        # Get login page
        try:
            self.br.open(Utils.UNIGRID_LOGIN_URL)
        except urllib2.URLError:
            raise Utils.ServerException("Could not contact the Uni-grid server")

        form = self.br.select_form(nr=0)
        self.br.set_all_readonly(False)

        # Set login values
        user = self.login_field.getText()
        if user and passw:
            self.br.set_value(user, name="user[short_name]")
            self.br.set_value(passw, name="user[password]")
            res = None
            try:
                res = self.br.submit()
            except urllib2.HTTPError as e:
                fail_msg = "Uni-grid login failed. Server response: {}".format(e)
                self.server_log(fail_msg)
                raise Utils.ServerException(fail_msg)

            # Check login success
            if res.geturl() == Utils.UNIGRID_LOGIN_URL:
                fail_msg = "Uni-grid login rejected. Check your username and password."
                self.server_log(fail_msg)
                raise Utils.ServerException(fail_msg)
            self.server_log("Logged in as {}".format(user))
            self.active_login = user
        else:
            self.server_log("No login info provided. Rendering as guest")

    def upload(self, job):
        # Login
        try:
            self.login(self.login_field.getText(), self.password)
        except Utils.ServerException as e:
            confirmDialog(title="Uni-grid error", message=str(e))
            return

        # Get new job page
        self.br.open(Utils.UNIGRID_NEW_JOB_URL)
        self.br.select_form(id="new_job")
        self.br["job[job_type]"] = ["Arnold"]

        # Set job variables
        scene_name = os.path.basename(system.sceneName())
        self.br.set_value(self.email_field.getText(), name="job[email]")
        self.br.set_value(scene_name, name="job[scene]")

        # Fixed start frame at 1 so the server can index into the manifest correctly
        self.br.set_value("1", name="job[start_frame]")
        self.br.set_value(str(self.cols.getValue() * self.rows.getValue() * ((self.end_frame.getValue() - self.start_frame.getValue() + 1))), name="job[end_frame]")
        self.br.form.add_file(open(job.zip_path, 'rb'), 'application/zip', job.zip_path, name="job[project_zip]")
        res = self.br.submit()

        # Check job submission success
        job_id = None
        if res.geturl() == Utils.UNIGRID_JOBS_URL:
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

        # Store job locally
        self.store_job(job.job_id, scene_name)

        # Let stitcher know new job has been queued
        self.stitch_remote(job.job_id)

    def stop(self):
        self.poll_running = False

    def stitch_poller(self):
        while self.poll_running:
            self.update_jobs()
            time.sleep(STITCH_POLL_TIME)
        print("Exiting poller")

    def stitch_remote(self, job_id):
        self.server_log("Submitting stitch job to {}".format(self.stitch_url.getText()))
        
        # POST request to the stitch server letting it know to watch for a completed Uni-grid job
        args = urllib.urlencode({'job_id': job_id})
        request = urllib2.Request("{}/stitch".format(self.stitch_url.getText()), args)
        response = urllib2.urlopen(request)
        self.server_log("Stitch server respose code: {}".format(response.getcode()))

    def refresh_cameras(self, *args):
        optionMenu(self.camera_list, edit=True, deleteAllItems=True)
        self.camera_list.addItems([cam.name() for cam in ls(cameras=True) if cam.renderable.get()])

    # Callback functions
    def toggle_debug_items(self, *args):
        frameLayout(self.debug_frame, edit=True, visible=not frameLayout(self.debug_frame, query=True, visible=True))

    def refresh_pressed(self, *args):
        # self.load_saved_jobs(os.path.basename(system.sceneName()))
        self.update_jobs(True)

    def exportPressed(self, *args):
        job = self.export()
        confirmDialog(title="Uni-grid", message="Manifest and zip located at\n{}".format(job.manifest_filepath))

    def exportAndUploadPressed(self, *args):
        job = self.export()
        if job:
            self.upload(job)

    def export_selective_changed(self, *args):
        enabled = self.export_selective_toggle.getValue()
        columnLayout(self.export_selective_layout, edit=True, enable=enabled, visible=enabled)

    def addAnimPressed(self, *args):
        for node in listRelatives(ls(selection=True), shapes=True):
            if not node:
                continue
            static_and_animated_items = textScrollList(self.animated_shape_nodes, query=True, allItems=True) + textScrollList(self.static_shape_nodes, query=True, allItems=True)
            if node.name() not in static_and_animated_items:
                self.animated_shape_nodes.append(node.name())

    def addStaticPressed(self, *args):
        for node in listRelatives(ls(selection=True), shapes=True):
            if not node:
                continue
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

        layout = columnLayout(adjustableColumn=True, height=200, rowSpacing=self.row_spacing, columnAlign="left", parent=missing_assets_win)
        text(label='The following nodes have missing external dependencies\nMake sure assets are relative to [PROJECT_FOLDER]/sourceimages!\nClick the entries below to inspect file paths.', align="left", parent=layout)
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
