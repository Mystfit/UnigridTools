from functools import partial
import os, json

class RenderJob(object):
    def __init__(self, **kwargs):
        self.unigrid_wd = os.path.normpath(os.path.join(workspace.getPath(), 'data', 'unigrid'))
        self.texture_folder_name = os.path.join("textures", "sourceimages")
        self.procedural_folder_name = "procedurals"
        self.source_tex_folder = os.path.join(workspace.getPath(), "sourceimages")
        self.ass_folder_name = os.path.join("ass", os.path.basename(os.path.splitext(system.sceneName())[0]))
        self.wd = os.path.normpath(os.path.join(self.unigrid_wd, os.path.basename(workspace.getName())))
        self.wd_textures = os.path.normpath(os.path.join(self.wd, self.texture_folder_name))
        self.wd_procedurals = os.path.normpath(os.path.joinself.wd, self.procedural_folder_name)
        self.wd_ass = os.path.normpath(os.path.join(self.wd, self.ass_folder_name))

        self.manifest = {}
        self.manifest["textures"] = []
        self.manifest["kick_flags"] = {}
        self.camera = kwargs["cam"] if "cam" in kwargs else None
        self.ass_filename_prefix = os.path.basename(os.path.splitext(sceneName())[0])
        self.default_args = {'asciiAss': True}
        self.file_extension = os.path.splitext(rendering.renderSettings(firstImageName=True)[0])[1][1:]
        self.zip_path = os.path.join(self.unigrid_wd, os.path.basename(workspace.getName())) + ".zip"
        self.missing_textures = []
        self.export_success = True
        self.init_render_options()

    def init_render_options(self):
        workspace.mkdir(self.wd)
        workspace.mkdir(self.wd_textures)
        workspace.mkdir(self.wd_procedurals)
        workspace.mkdir(self.wd_ass)
        cleanup_folder(self.wd_textures)
        cleanup_folder(self.wd_procedurals)
        cleanup_folder(self.wd_ass)

        # Get render option nodes
        self.arnold_opts = ls('defaultArnoldRenderOptions')[0]
        self.default_render_globals = ls('defaultRenderGlobals')[0]

        # Save original Arnold settings
        self.orig_absTexOpt = self.arnold_opts.absoluteTexturePaths.get()
        self.orig_abortOnLicenseFail = self.arnold_opts.abortOnLicenseFail.get()

        # Set Arnold properties
        self.arnold_opts.absoluteTexturePaths.set(0)
        self.arnold_opts.abortOnLicenseFail.set(1)

    def start(self):
        self.gather_assets()
        self.export_scenes()
        self.update_manifest()
        if self.export_success:
            self.zip_results()
        self.cleanup_render_options()

    def gather_assets(self):
        # Copy aiImage nodes
        for tex in ls(type='aiImage'):
            copied_tx = self.copy_tx(tex, tex.filename.get(), self.source_tex_folder, self.wd_textures)
            if copied_tx:
                self.manifest["textures"].append(tx)

        # Copy texture nodes
        for tex in ls(type='file'):
            copied_tx = self.copy_tx(tex, tex.fileTextureName.get(), self.source_tex_folder, self.wd_textures)
            if copied_tx:
                self.manifest["textures"].append(copied_tx)

        if self.missing_textures:
            self.export_success = False
            self.missing_textures_dialog()
            # layoutDialog(ui=self.missing_textures_dialog)
            # confirmDialog(title="Uni-grid error", message="Your scene has missing textures.\n\n{}".format(missing_textures))

    def export_scenes(start_frame=-1, end_frame=-1):
        raise RuntimeException("Not implemented")

    def update_manifest(self):
        # Manifest vars
        self.manifest["kick_flags"]["set"] = {
            "options.texture_searchpath": os.path.join("<PROJECT_PATH>", self.texture_folder_name),
            "options.procedural_searchpath": os.path.join("<PROJECT_PATH>", self.procedural_folder_name)
        }
        self.manifest["kick_flags"]["nostdin"] = ""
        self.manifest["kick_flags"]["dw"] = ""
        self.manifest["kick_flags"]["dp"] = ""
        self.manifest["kick_flags"]["i"] = "<IN_FILE>"
        self.manifest["kick_flags"]["o"] ="<OUT_FILE>"

        # Write manifest
        manifest_filepath = os.path.join(self.wd, 'manifest.json')
        with open(manifest_filepath, 'w') as outfile:
            print("Writing manifest to " + manifest_filepath)
            manifest_s = json.dumps(self.manifest, indent=True).replace("\\\\", "/")
            outfile.write(manifest_s)

    def zip_results(self):
        print("Creating archive at: {}".format(os.path.join(self.unigrid_wd, os.path.basename(workspace.getName()))))
        zip_path = make_archive(os.path.splitext(self.zip_path)[0], 'zip', root_dir=self.unigrid_wd, base_dir=os.path.relpath(self.wd, self.unigrid_wd))
        print("Created Unigrid archive at {}".format(self.zip_path))

    def cleanup_render_options(self):
        # Reset original arnold values
        self.arnold_opts = ls('defaultArnoldRenderOptions')[0]
        self.arnold_opts.absoluteTexturePaths.set(self.orig_absTexOpt)
        self.arnold_opts.abortOnLicenseFail.set(self.orig_abortOnLicenseFail) 

    # Copy textures helper function
    def copy_tx(self, node, file_path, path_prefix, dest_path):
        if not file_path or not dest_path:
            return None

        rel_path = os.path.relpath(file_path, path_prefix)
        source_file = "{}.tx".format(os.path.splitext(file_path)[0])
        dest_path = os.path.join(dest_path, os.path.dirname(rel_path))
        workspace.mkdir(dest_path)
        print("Copying {} to {}".format(source_file, dest_path))
        try:
            copy2(source_file, dest_path)
        except IOError as e:
            print("Exception during texture copy: {}".format(e))
            self.missing_textures.append(node)
            return None
        return os.path.relpath(os.path.join(dest_path, source_file), path_prefix)

    def missing_textures_dialog(self):
        missing_textures_win = window(title="Uni-grid export error", width=500, height=220)
        missing_textures_win.show()

        layout = columnLayout(adjustableColumn=True, height=200, rowSpacing=4, columnAlign="left", parent=missing_textures_win)
        text(label='The following nodes have missing tx files (click to select):', align="left", parent=layout)
        missing_texture_list = textScrollList("missing_texture_list", height=200, parent=layout)
        textScrollList(missing_texture_list, edit=True, sc=partial(goto_missing_texture, missing_texture_list))
        for tex in self.missing_textures:
            missing_texture_list.append(tex.name())


def goto_missing_texture(scrollList):
    node = textScrollList(scrollList, query=True, si=True)
    if node:
        print("Missing texture node: {}".format(node[0]))
        select(node[0])
    return ""

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
