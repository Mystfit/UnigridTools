import os, json
from shutil import copy2, make_archive

from pymel.core import *
from arnold import *
import Utils
import maya.app.renderSetup.model.renderSetup as renderSetup


class RenderJobException(Exception):
    pass

class MissingAssetException(Exception):
    def __init__(self, data):
        self.missing_assets = data

class RenderJob(object):
    def __init__(self, **kwargs):
        # Create paths
        self.unigrid_wd = os.path.normpath(os.path.join(workspace.getPath(), 'data', 'unigrid'))
        self.texture_folder_name = os.path.join("textures", "sourceimages")
        self.procedural_folder_name = "procedurals"
        self.source_tex_folder = os.path.join(workspace.getPath(), "sourceimages")
        self.ass_folder_name = os.path.join("ass", os.path.basename(os.path.splitext(system.sceneName())[0]))
        self.name = workspace.getName().replace(" ", "_")
        self.wd = os.path.normpath(os.path.join(self.unigrid_wd, os.path.basename(self.name)))
        self.wd_textures = os.path.normpath(os.path.join(self.wd, self.texture_folder_name))
        self.wd_procedurals = os.path.normpath(os.path.join(self.wd, self.procedural_folder_name))
        self.wd_ass = os.path.normpath(os.path.join(self.wd, self.ass_folder_name))
        self.anim_path = os.path.normpath(os.path.join(self.wd_ass, "frames"))

        # Create manifest
        self.manifest = {}
        self.manifest["textures"] = []
        self.manifest["kick_flags"] = {}
        self.camera = kwargs["cam"] if "cam" in kwargs else None
        self.ass_filename_prefix = os.path.basename(os.path.splitext(sceneName())[0])
        self.default_args = {'asciiAss': True}
        self.file_extension = os.path.splitext(rendering.renderSettings(firstImageName=True)[0])[1][1:]
        self.zip_path = self.wd + ".zip"
        self.missing_textures = []
        self.default_resource_args = { 
            "asciiAss": True,
            "cam": self.camera.name()
        }

    def export(self):
        self.init_render_options()
        self.cleanup_workspace()
        self.gather_assets()
        self.export_scene()
        self.update_manifest()
        self.zip_results()
        self.cleanup_render_options()

    def cleanup_workspace(self):
        workspace.mkdir(self.wd)
        workspace.mkdir(self.wd_textures)
        workspace.mkdir(self.wd_procedurals)
        workspace.mkdir(self.wd_ass)
        Utils.cleanup_folder(self.wd_textures)
        Utils.cleanup_folder(self.wd_procedurals)
        Utils.cleanup_folder(self.wd_ass)

    def init_render_options(self):
        # Get render option nodes
        arnold_opt_nodes = ls('defaultArnoldRenderOptions')
        if not arnold_opt_nodes:
            raise RenderJobException("Missing Arnold options. Please open the Render Settings window at least once.")

        self.arnold_opts = arnold_opt_nodes[0]
        self.default_render_globals = ls('defaultRenderGlobals')[0]

        # Save original Arnold settings
        self.orig_absTexOpt = self.arnold_opts.absoluteTexturePaths.get()
        self.orig_abortOnLicenseFail = self.arnold_opts.abortOnLicenseFail.get()

        # Set Arnold properties
        self.arnold_opts.absoluteTexturePaths.set(0)
        self.arnold_opts.abortOnLicenseFail.set(1)
        return True

    def gather_assets(self):
        # Copy aiImage nodes
        for tex in ls(type='aiImage'):
            copied_tx = self.copy_tx(tex, tex.filename.get(), self.source_tex_folder, self.wd_textures)
            if copied_tx:
                self.manifest["textures"].append(copied_tx)

        # Copy texture nodes
        for tex in ls(type='file'):
            copied_tx = self.copy_tx(tex, tex.fileTextureName.get(), self.source_tex_folder, self.wd_textures)
            if copied_tx:
                self.manifest["textures"].append(copied_tx)

        if self.missing_textures:
            raise MissingAssetException(self.missing_textures)

    def export_scene(self):
        # Export render layers individually
        with Utils.maintained_render_layer():
            for renderable_layer in Utils.get_renderable_layers():
                renderSetup.instance().switchToLayer(renderable_layer)
                self.ai_export()

    def ai_export(self):
        MAYA_COLOUR_MANAGER = 2048

        # Create frame args
        layer = renderSetup.instance().getVisibleRenderLayer()
        frame = int(currentTime(query=True))
        animated_resource_args = {
            "f": "{}.{}.{}".format(os.path.normpath(os.path.join(self.anim_path, self.ass_filename_prefix)), layer.name(), str(frame).zfill(4)),
            "mask": AI_NODE_ALL ^ MAYA_COLOUR_MANAGER
        }

        # Add animated nodes to select flag
        anim_nodes = []
        if self.animated_nodes:
            anim_nodes = self.animated_nodes
            animated_resource_args["s"] = True
        animated_resource_args.update(self.default_resource_args)

        # Export animated resources
        arnoldExportAss(*anim_nodes, **animated_resource_args)
        resources = ["{}.ass".format(os.path.relpath(animated_resource_args["f"], self.wd))] + self.shared_resources
        
        # Export tiles
        resolution = ls('defaultResolution')[0]
        tiles = []
        if self.dynamic_tiles:
            tiles = self.export_tiles(frame, layer, 1, 1, resolution.width.get(), resolution.height.get())
        else:
            tiles = self.export_tiles(frame, layer, self.rows, self.cols, resolution.width.get(), resolution.height.get())

        # Group frame/tile resources into manifest
        self.manifest["frames"].append({
            "outfile": "{}.{}".format(os.path.relpath(os.path.join(self.image_path, os.path.basename(animated_resource_args["f"])), self.wd), self.file_extension),
            "res_x": resolution.width.get(),
            "res_y": resolution.height.get(),
            "resources": resources,
            "tiles": tiles
        })

    def export_tiles(self, frame, layer, rows, cols, width, height):
        tile_width = abs(width / cols)
        tile_height = abs(height / rows)
        tile_leftover_width = width % cols
        tile_leftover_height= height % rows
        tiles = []

        for col in range(cols):
            # Create tile coordinates
            tile_left = col * tile_width
            tile_right = (col + 1) * tile_width 
            if col == cols - 1:
                tile_right += tile_leftover_width
            for row in range(rows):
                tile_top = row * tile_height
                tile_bottom = (row + 1) * tile_height
                if row == rows - 1:
                    tile_bottom += tile_leftover_height

                # Export tile
                coords = [tile_left, tile_top, tile_right, tile_bottom]
                tiles.append({
                    "outfile": "{}_tile_{}-{}.{}.{}.{}".format(os.path.relpath(os.path.join(self.tile_path, self.ass_filename_prefix), self.wd), col, row, layer.name(), str(frame).zfill(4), self.file_extension),
                    "coords": coords,
                    "kick_flags": {
                        "rg": " ".join(str(tile) for tile in coords)
                    }
                })

        return tiles

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
        self.manifest_filepath = os.path.join(self.wd, 'manifest.json')
        with open(self.manifest_filepath, 'w') as outfile:
            print("Writing manifest to " + self.manifest_filepath)
            manifest_s = json.dumps(self.manifest, indent=True).replace("\\\\", "/")
            outfile.write(manifest_s)

    def zip_results(self):
        zip_path = make_archive(os.path.splitext(self.zip_path)[0], 'zip', root_dir=self.unigrid_wd, base_dir=os.path.relpath(self.wd, self.unigrid_wd))
        print("Created Unigrid archive at {}".format(self.zip_path))

    def cleanup_render_options(self):
        # Reset original arnold values
        arnold_opts = ls('defaultArnoldRenderOptions')[0]
        arnold_opts.absoluteTexturePaths.set(self.orig_absTexOpt)
        arnold_opts.abortOnLicenseFail.set(self.orig_abortOnLicenseFail) 

    # Copy textures helper function
    def copy_tx(self, node, file_path, path_prefix, dest_path):
        if not file_path or not dest_path:
            return None
        rel_path = None

        try:
            rel_path = os.path.relpath(file_path, path_prefix)
        except ValueError as e:
            print("Value during texture copy: {}".format(e))
            self.missing_textures.append(node)
            return None

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
