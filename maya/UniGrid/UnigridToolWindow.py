from pymel.core import *
from pymel import *

import os, sys, ssl, mechanize, platform, threading

import RenderJob
reload(RenderJob)
from RenderJob import RenderJobException, RenderJobAssetException

import AnimRenderJob
reload(AnimRenderJob)
from AnimRenderJob import AnimRenderJob

def popenAndCall(popenArgs, onExit):
    """
    Runs the given args in a subprocess.Popen, and then calls the function
    onExit when the subprocess completes.
    onExit is a callable object, and popenArgs is a list/tuple of args that 
    would give to subprocess.Popen.
    """
    def runInThread(popenArgs, onExit):
        print("Running command {}".format(" ".join(popenArgs)))
        os.system(" ".join(popenArgs))
        return

    thread = threading.Thread(target=runInThread, args=(popenArgs, onExit))
    thread.start()
    return thread


class UnigridToolWindow(object):

    def create_GUI(self):
        # Window
        print("Creating gui")
        self.win = window(title="Unigrid Export", width=500)
        self.layout = columnLayout(adjustableColumn=True, rowSpacing=4, columnAlign="left", parent=self.win)

        # Login

        login_attachments = ["left" for i in range(6)]
        self.login_frame = frameLayout(collapsable=False, label="Login", marginHeight=2, marginWidth=2, parent=self.layout)
        self.login_layout = rowLayout(parent=self.login_frame, numberOfColumns=6, columnAttach6=login_attachments, columnAlign6=login_attachments, adjustableColumn=6)
        self.password = ""
        self.password_field = None

        # self.userpass_layout = flowLayout(columnSpacing=2, parent=self.login_layout)
        self.login_label = text(label='Username:', align='center', parent=self.login_layout)
        self.login_field = textField(text="", width=100, parent=self.login_layout)
        self.password_label = text(label='Password:', align='center', parent=self.login_layout)
        self.password_field = textField(width=100, changeCommand=self.hidePassword, parent=self.login_layout)
        
        self.email_label = text(label='Email:', align='center', parent=self.login_layout)
        self.email_field = textField(text="", width=100, parent=self.login_layout)

        # Tiles
        self.tile_frame = frameLayout(collapsable=True, collapse=True, label="Tiles", marginHeight=2, marginWidth=2, parent=self.layout)
        self.tile_layout = columnLayout(adjustableColumn=True, rowSpacing=4, columnAlign="left", parent=self.tile_frame)
        self.dyn_tiles_toggle = checkBox(label="Dynamic tiles", value=False, visible=False, parent=self.tile_layout)
        
        rowcol_attachments = ["left" for i in range(4)]
        self.row_col_layout = rowLayout(parent=self.tile_layout, numberOfColumns=4, columnAttach4=rowcol_attachments, columnAlign4=rowcol_attachments)
        self.col_text = text(label="Columns:", align='center', parent=self.row_col_layout)
        self.cols = intField(value=1, parent=self.row_col_layout, width=100)
        self.row_text = text(label="Rows:", align='center', parent=self.row_col_layout)
        self.rows = intField(value=1, parent=self.row_col_layout, width=100)

        # Tile stitching
        job_path_attachments = ["left", "left", "right"]
        self.job_path_layout = rowLayout(parent=self.tile_layout, numberOfColumns=3, columnAttach3=job_path_attachments, columnAlign3=job_path_attachments, adjustableColumn=2)
        self.tiles_path_label = text(label='Tile path:', parent=self.job_path_layout)
        self.tiles_path = textField(text="/Volumes/uni-grid/renders/[YOUR_USER_NAME]/[JOB_ID]", parent=self.job_path_layout)
        self.tiles_path_browse_btn = iconTextButton(style="iconOnly", image1="folder-open.png", parent=self.job_path_layout)
        self.stitch_btn = button(label="Stitch tiles", parent=self.tile_layout)

        # Exported objects
        self.exported_frame = frameLayout(collapse=True, collapsable=True, label="Export settings", marginHeight=2, marginWidth=2, parent=self.layout)
        self.exported_layout = columnLayout(adjustableColumn=True, rowSpacing=4, columnAlign="left", parent=self.exported_frame)

        # Cameras
        self.camera_list = optionMenu(label="Camera", parent=self.exported_layout)
        self.camera_list.addItems([cam.name() for cam in ls(cameras=True) if cam.renderable.get()])

        # Frames
        frame_attachments = ["left" for i in range(4)]
        self.frames_layout = rowLayout(parent=self.exported_layout, numberOfColumns=4, columnAttach4=frame_attachments, columnAlign4=frame_attachments)
        self.start_frame_text = text(label="Start frame:", align='center', parent=self.frames_layout)
        self.start_frame = intField(value=1, parent=self.frames_layout, width=100)
        self.end_frame_text = text(label="End frame:", align='center', parent=self.frames_layout)
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

        separator(height=10, parent=self.layout)

        # Upload
        self.upload_frame = frameLayout(collapsable=False, collapse=False, labelVisible=False, label="Upload", marginHeight=2, marginWidth=2, parent=self.layout)
        self.upload_layout = columnLayout(adjustableColumn=True, rowSpacing=4, columnAlign="left", parent=self.upload_frame)
        self.export_btn = button(label="Export manifest", parent=self.upload_layout)
        self.export_upload_btn = button(label="Export and upload to Uni-grid", parent=self.upload_layout)

        # Add callbacks to buttons
        self.export_btn.setCommand(self.exportPressed)
        self.export_upload_btn.setCommand(self.exportAndUploadPressed)
        self.add_anim_shape_btn.setCommand(self.addAnimPressed)
        self.remove_anim_shape_btn.setCommand(self.removeAnimPressed)
        self.add_static_shape_btn.setCommand(self.addStaticPressed)
        self.remove_static_shape_btn.setCommand(self.removeStaticPressed)
        self.tiles_path_browse_btn.setCommand(self.setTilePathPressed)
        self.stitch_btn.setCommand(self.stitchPressed)

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
        unigrid_url = 'https://uni-grid.mddn.vuw.ac.nz'
        unigrid_login_url = unigrid_url + "/login"
        unigrid_new_job_url = unigrid_url + "/jobs/new"

        ssl._create_default_https_context = ssl._create_unverified_context
        br = mechanize.Browser()
        br.set_handle_robots(False) # ignore robots
        br.open(unigrid_login_url)
        form = br.select_form(nr=0)
        br.set_all_readonly(False)

        br.set_value(self.login_field.getText(), name="user[short_name]")
        br.set_value(self.password, name="user[password]")
        res = br.submit()
        if res.geturl() == unigrid_login_url:
            print("Login failed")
            confirmDialog(title="Uni-grid", message="Uni-grid login rejected. Check your username and password.")
            return        
        print("Login successful")

        br.open(unigrid_new_job_url)
        br.select_form(id="new_job")
        br["job[job_type]"] = ["Arnold"]
        br.set_value(self.email_field.getText(), name="job[email]")
        br.set_value(os.path.basename(system.sceneName()), name="job[scene]")
        br.set_value(str(self.start_frame.getValue()), name="job[start_frame]")
        br.set_value(str(self.cols.getValue() * self.rows.getValue() * ((self.end_frame.getValue() - self.start_frame.getValue() + 1))), name="job[end_frame]")
        br.form.add_file(open(job.zip_path, 'rb'), 'application/zip', job.zip_path, name="job[project_zip]")
        res = br.submit()

        job_id = None
        if res.geturl() == unigrid_new_job_url:
            print(res.read())
            confirmDialog(title="Uni-grid error", message="Uni-grid server rejected the render job. Check your settings.")
            return
        
        job.job_id = res.geturl().split("/")[-1]
        job_tile_render_path = ""
        if platform.system() == "Windows":
            job_tile_render_path = "\\\\uni-grid.mddn.vuw.ac.nz\\uni-grid\\renders\\{}\\{}".format(self.login_field.getText(), job.job_id)
        elif platform.system() == "Darwin":
            job_tile_render_path = "/Volumes/uni-grid/renders/{}/{}".format(self.login_field.getText(), job.job_id)
        self.tiles_path.setText(job_tile_render_path)
        confirmDialog(title="Uni-grid", message="Render submitted successfully.\n\nJob ID: {}".format(job.job_id))

    # Callback functions
    def exportPressed(self, *args):
        self.export()

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

    def setTilePathPressed(self, *args):
        self.tiles_path.setText(promptForFolder())

    def stitchPressed(self, *args):
        stitch_script_path = os.path.join(workspace.getPath(), "scripts", "unigrid_stitch.py")
        manifest_path = os.path.join(self.wd, 'manifest.json')
        num_threads = 8
        stitch_cmd = [str(flag) for flag in [stitch_script_path, manifest_path, self.tiles_path.getText(), workspace.getPath(), num_threads]]
        if platform.system() == "Darwin":
            # UUUUUUGH, hardcoded paths :(
            stitch_cmd.insert(0, "/usr/local/bin/python")
        elif platform.system() == "Windows":
            stitch_cmd.insert(0, "python")
        print(" ".join(stitch_cmd))
        popenAndCall(stitch_cmd, self.stitch_complete)
        confirmDialog(title="Uni-grid", message="Tile stitching in progress. This may take a while.\n\nStitched frames are located at {}/images".format(workspace.getPath()))
        print("Done!")

    def stitch_complete(self):
        confirmDialog(title="Uni-grid", message="Tile stitching complete.")

    def missing_assets_dialog(self, missing_asset_nodes):
        missing_assets_win = window(title="Uni-grid export error", width=500, height=220)
        missing_assets_win.show()

        layout = columnLayout(adjustableColumn=True, height=200, rowSpacing=4, columnAlign="left", parent=missing_assets_win)
        text(label='The following nodes have missing external dependencies. Check your paths!\nClick to select:', align="left", parent=layout)
        missing_asset_list = textScrollList("missing_texture_list", height=200, parent=layout)
        textScrollList(missing_asset_list, edit=True, sc=partial(goto_missing_asset, missing_asset_list))
        for asset in missing_asset_nodes:
            missing_asset_list.append(asset.name())


def goto_missing_asset(scrollList):
    node = textScrollList(scrollList, query=True, si=True)
    if node:
        print("Missing asset node: {}".format(node[0]))
        select(node[0])
    return ""

