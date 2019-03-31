import os
from pymel.core import *
from arnold import *

from RenderJob import RenderJob
import Utils

class AnimRenderJob(RenderJob):
    def __init__(self, start_frame, end_frame, **kwargs):
        super(AnimRenderJob, self).__init__(**kwargs)
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.dynamic_tiles = kwargs["dynamic_tiles"] if "dynamic_tiles" in kwargs else False
        self.cols = kwargs["cols"] if "cols" in kwargs and not self.dynamic_tiles else 1
        self.rows = kwargs["rows"] if "rows" in kwargs and not self.dynamic_tiles else 1
        self.animated_nodes = kwargs["animated_nodes"] if "animated_nodes" in kwargs else None
        self.static_nodes = kwargs["static_nodes"] if "static_nodes" in kwargs else None
        self.shared_resources = []
        self.manifest["frames"] = []

        self.image_path = os.path.normpath(os.path.join(self.wd, "images"))
        self.tile_path = os.path.normpath(os.path.join(self.wd, "images", "tiles"))
        self.static_path = os.path.normpath(os.path.join(self.wd_ass, "static"))

    def init_render_options(self):
        if not super(AnimRenderJob, self).init_render_options():
            return False
        self.orig_leftRegion = self.arnold_opts.regionMinX.get()
        self.orig_rightRegion = self.arnold_opts.regionMaxX.get()
        self.orig_topRegion = self.arnold_opts.regionMinY.get()
        self.orig_bottomRegion = self.arnold_opts.regionMaxY.get()
        return True

    def cleanup_workspace(self):
        workspace.mkdir(self.tile_path)
        workspace.mkdir(self.static_path)
        workspace.mkdir(self.anim_path)
        Utils.cleanup_folder(self.tile_path)
        Utils.cleanup_folder(self.static_path)
        Utils.cleanup_folder(self.anim_path)

    def gather_assets(self):
        # Copy file nodes
        animated_textures = []

        for tex in ls(type='file'):
            if(tex.useFrameExtension.get() == 1):
                animated_textures.append(tex)

        # Copy frame specific files
        for frame in range(self.start_frame, self.end_frame):
            # Advance timeline
            animation.currentTime(frame)

            # Save scene file in manifest
            for tex in animated_textures:
                tex_frame = tex.frameExtension.get() + tex.frameOffset.get()
                tex_frame_file = tex.computedFileTextureNamePattern.get().replace('<f>', str(tex_frame))
                copied_tx = self.copy_tx(tex, tex_frame_file, self.source_tex_folder, self.wd_textures)
                if copied_tx:
                    self.manifest["textures"].append(copied_tx)

        super(AnimRenderJob, self).gather_assets()


    def export_scene(self):
        MAYA_COLOUR_MANAGER = 2048

        # Args for the static ass scene
        static_resource_args = {
            "f": "{}_static".format(os.path.normpath(os.path.join(self.static_path, self.ass_filename_prefix))),
            "mask": AI_NODE_ALL ^ AI_NODE_OPTIONS ^ AI_NODE_DRIVER ^ AI_NODE_FILTER ^ MAYA_COLOUR_MANAGER
        }
        static_resource_args.update(self.default_resource_args)

        if self.static_nodes:
            static_nodes = self.static_nodes if self.static_nodes else []
            # Remove animated nodes from static resources
            static_resource_args['s'] = True

            # Export static resources
            arnoldExportAss(*static_nodes, **static_resource_args)
            self.shared_resources.append("{}.ass".format(os.path.relpath(static_resource_args["f"], self.wd)))

        # Export tiles per frame
        for frame in range(self.start_frame, self.end_frame + 1):
            # Advance timeline
            print("Exporting frame {}".format(frame))
            animation.currentTime(frame)
            super(AnimRenderJob, self).export_scene()

    def cleanup_render_options(self):
        super(AnimRenderJob, self).cleanup_render_options()
        self.arnold_opts.regionMinX.set(self.orig_leftRegion)
        self.arnold_opts.regionMaxX.set(self.orig_rightRegion)
        self.arnold_opts.regionMinY.set(self.orig_topRegion)
        self.arnold_opts.regionMaxY.set(self.orig_bottomRegion)
