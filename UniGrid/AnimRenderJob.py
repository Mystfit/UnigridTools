from .RenderJob import RenderJob

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
        self.manifest["frames"] = []

    def init_render_options(self):
        super(AnimRenderJob, self).init_render_options()
        self.orig_leftRegion = self.arnold_opts.regionMinX.get()
        self.orig_rightRegion = self.arnold_opts.regionMaxX.get()
        self.orig_topRegion = self.arnold_opts.regionMinY.get()
        self.orig_bottomRegion = self.arnold_opts.regionMaxY.get()
        
        self.image_path = os.path.normpath(os.path.join(self.wd, "images"))
        self.tile_path = os.path.normpath(os.path.join(self.wd, "images", "tiles"))
        self.static_path = os.path.normpath(os.path.join(self.wd_ass, "static"))
        self.anim_path = os.path.normpath(os.path.join(self.wd_ass, "frames"))
        workspace.mkdir(self.tile_path)
        workspace.mkdir(self.static_path)
        workspace.mkdir(self.anim_path)
        cleanup_folder(self.tile_path)
        cleanup_folder(self.static_path)
        cleanup_folder(self.anim_path)

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


    def export_scenes(self):
        # Export new camera ass scene with render region set
        resource_args = { 
            "asciiAss": True,
            "cam": self.camera.name()
        }

        MAYA_COLOUR_MANAGER = 2048

        # Args for the static ass scene
        static_resource_args = {
            "f": "{}_static".format(os.path.normpath(os.path.join(self.static_path, self.ass_filename_prefix))),
            "mask": AI_NODE_ALL ^ AI_NODE_OPTIONS ^ AI_NODE_DRIVER ^ AI_NODE_FILTER ^ MAYA_COLOUR_MANAGER
        }
        static_resource_args.update(resource_args)

        static_resources = []
        if self.static_nodes:
            static_nodes = self.static_nodes if self.static_nodes else []
            # Remove animated nodes from static resources
            static_resource_args['s'] = True

            # Export static resources
            arnoldExportAss(*static_nodes, **static_resource_args)
            static_resources.append("{}.ass".format(os.path.relpath(static_resource_args["f"], self.wd)))

        # Export tiles per frame
        for frame in range(self.start_frame, self.end_frame + 1):
            # Advance timeline
            print("Exporting frame {}".format(frame))
            animation.currentTime(frame)

            # Create frame args
            animated_resource_args = {
                "f": "{}.{}".format(os.path.normpath(os.path.join(self.anim_path, self.ass_filename_prefix)), str(frame).zfill(4)),
                "mask": AI_NODE_ALL ^ MAYA_COLOUR_MANAGER
            }
            anim_nodes = []
            if self.animated_nodes:
                anim_nodes = self.animated_nodes
                animated_resource_args["s"] = True
            animated_resource_args.update(resource_args)

            # Export animated resources
            arnoldExportAss(*anim_nodes, **animated_resource_args)
            resources = ["{}.ass".format(os.path.relpath(animated_resource_args["f"], self.wd))] + static_resources
            
            # Export tiles
            resolution = ls('defaultResolution')[0]
            tiles = []
            if self.dynamic_tiles:
                print("Getting dynamic tiles")
                tiles = self.export_frame_tiles(frame, 1, 1, resolution.width.get(), resolution.height.get())
            else:
                print("Getting regular tiles")
                tiles = self.export_frame_tiles(frame, self.rows, self.cols, resolution.width.get(), resolution.height.get())

            # Group frame/tile resources into manifest
            self.manifest["frames"].append({
                "outfile": "{}.{}".format(os.path.relpath(os.path.join(self.image_path, os.path.basename(animated_resource_args["f"])), self.wd), self.file_extension),
                "res_x": resolution.width.get(),
                "res_y": resolution.height.get(),
                "resources": resources,
                "tiles": tiles
            })


    def export_frame_tiles(self, frame, rows, cols, width, height):
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
                print("Adding tile {}x, {}y".format(col, row))
                tiles.append({
                    "outfile": "{}_tile_{}-{}.{}.{}".format(os.path.relpath(os.path.join(self.tile_path, self.ass_filename_prefix), self.wd), col, row, str(frame).zfill(4), self.file_extension),
                    "coords": coords,
                    "kick_flags": {
                        "rg": " ".join(str(tile) for tile in coords)
                    }
                })

        return tiles

    def cleanup_render_options(self):
        super(AnimRenderJob, self).cleanup_render_options()
        self.arnold_opts.regionMinX.set(self.orig_leftRegion)
        self.arnold_opts.regionMaxX.set(self.orig_rightRegion)
        self.arnold_opts.regionMinY.set(self.orig_topRegion)
        self.arnold_opts.regionMaxY.set(self.orig_bottomRegion)
