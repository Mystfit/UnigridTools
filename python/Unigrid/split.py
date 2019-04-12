import os
import sys
import json
import math
import Unigrid.render
import copy
import argparse

try:
    import OpenImageIO as oiio
except ImportError:
    from oiio import OpenImageIO as oiio

class QuadSplit(object):
    def __init__(self, bounds, depth, max_depth, channels, threshold):
        self.threshold = threshold
        self.bounds = bounds
        self.depth = depth
        self.max_depth = max_depth
        self.children = []
        self.channels = channels

    def test_image(self, image_buf):
        threshold = (self.threshold / self.max_depth) * self.depth
        pixel_total = 0
        num_pixels = 0
        stride_x = int(math.ceil((threshold / float(self.threshold)) * self.bounds.width() / 10))
        stride_y = int(math.ceil((threshold / float(self.threshold)) * self.bounds.height() / 10))
        print("Testing bounds x:{}, y:{}, w:{}, h:{} against threshold:{} strideX:{} strideY:{}".format(self.bounds.xmin(), self.bounds.ymin(), self.bounds.width(), self.bounds.height(), threshold, stride_x, stride_y))
        for z in range(image_buf.spec().depth):
            for y in range(self.bounds.ymin(), self.bounds.ymax(), stride_y):
                for x in range(self.bounds.xmin(), self.bounds.xmax(), stride_x):
                    for channel in self.channels:
                        print("Channel: {} Channel index: {} X: {} Y: {} Z: {}".format(channel, image_buf.spec().channelindex(channel), x, y, z))
                        print(type(image_buf), type(x), type(y), type(z), type(image_buf.spec().channelindex(channel)))
                        if image_buf.getchannel(x, y, z, image_buf.spec().channelindex(channel)) > threshold:
                            self.split(image_buf)
                            return

    def split(self, image_buf):
        if self.depth < self.max_depth and self.bounds.width() >= 8 and self.bounds.height() >= 8:
            self.children.append(QuadSplit(Rect(self.bounds.xmin(), self.bounds.center()[0], self.bounds.ymin(), self.bounds.center()[1]), self.depth+1, self.max_depth, self.channels, self.threshold))
            self.children.append(QuadSplit(Rect(self.bounds.center()[0], self.bounds.xmax(), self.bounds.ymin(), self.bounds.center()[1]), self.depth+1, self.max_depth, self.channels, self.threshold))
            self.children.append(QuadSplit(Rect(self.bounds.xmin(), self.bounds.center()[0], self.bounds.center()[1], self.bounds.ymax()), self.depth+1, self.max_depth, self.channels, self.threshold))
            self.children.append(QuadSplit(Rect(self.bounds.center()[0], self.bounds.xmax(), self.bounds.center()[1], self.bounds.ymax()), self.depth+1, self.max_depth, self.channels, self.threshold))

            for child in self.children:
                child.test_image(image_buf)

    def get_quads(self):
        if len(self.children):
            quads = []
            for child in self.children:
                quads += child.get_quads()
            return quads
        return [[self.bounds.x1, self.bounds.y1, self.bounds.x2, self.bounds.y2]]


class Rect(object):
    def __init__(self, x1, x2, y1, y2):
        self.x1 = x1
        self.x2 = x2
        self.y1 = y1
        self.y2 = y2

    def xmin(self):
        return self.x1

    def xmax(self):
        return self.x2

    def ymin(self):
        return self.y1

    def ymax(self):
        return self.y2

    def width(self):
        # return max(self.x2 - self.x1, 0)
        return self.x2 - self.x1

    def height(self):
        # return max(self.y2 - self.y1, 0)
        return self.y2 - self.y1

    def center(self):
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)

    def __str__(self):
        return "x:{}, y:{}, w:{}, h:{}".format(self.x1, self.y1, self.width(), self.height())



def tiles_from_heatmap(frame, area, depth, threshold, flags, source, destination):
    # Calculate resized heatmap size using total area
    aspect = float(frame["res_x"]) / float(frame["res_y"])
    height = math.sqrt(area / aspect)
    width = height * aspect
    print("Heatmap Aspect: {} Width: {} Height: {}".format(aspect, width, height))

    # Render cpu tilemaps
    heatmap_frame_path = str(os.path.join(destination, frame["outfile"]))

    kick_command = r"C:\solidangle\mtoadeploy\2018\bin\kick.exe"
    Unigrid.render.render_frame_heatmap(kick_command, frame, width, height, flags, source, heatmap_frame_path)

    # Load rendered heatmaps
    frame_buf = oiio.ImageBuf(str(os.path.join(destination, frame["outfile"])))
    orig_spec = oiio.ImageSpec(frame_buf.spec())
    orig_spec.width = frame["res_x"]
    orig_spec.full_width = frame["res_x"]
    orig_spec.height = frame["res_y"]
    orig_spec.full_height = frame["res_y"]

    resized_frame_buf = oiio.ImageBuf(orig_spec)
    oiio.ImageBufAlgo.resize(resized_frame_buf, frame_buf)

    # Create tiles from resized images
    quadtree = QuadSplit(Rect(0, resized_frame_buf.spec().width, 0, resized_frame_buf.spec().height), 1, depth, ["raycount"], threshold)
    quadtree.test_image(resized_frame_buf)
    return quadtree.get_quads()


def add_tiles_to_frame(tiles, frame):
    for i in range(len(tiles)):
        tile = tiles[i]
        if "tiles" not in frame:
            frame["tiles"] = []
        extsplit = os.path.splitext(frame["outfile"])
        framesplit = os.path.splitext(extsplit[0])

        frame["tiles"].append({
            "outfile": "{}_t{}{}{}".format(framesplit[0], i, framesplit[1], extsplit[1]),
            "coords": [tile[0], tile[1], tile[2], tile[3]],
            "kick_flags": {
                "rg": " ".join(str(tile) for tile in [tile[0], tile[1], tile[2], tile[3]])
            }
        })
    return frame


def run_splitter(**kwargs):
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', help='Input manifest file')
    parser.add_argument('-f', '--frame', default=None, type=int, help='Frame to split')
    parser.add_argument('-o', '--output-dir', default=os.path.join(os.getcwd(), "heatmaps"), help='Output heatmap dir')
    parser.add_argument('-a', '--area', default=10000, type=int, help='Area of heatmap')
    parser.add_argument('-d', '--depth', default=6, type=int, help='Tile recurse depth')
    parser.add_argument('-t', '--threshold', default=60, type=int, help='Tile threshold')
    args = parser.parse_args()

    manifest_path = args.manifest
    manifest_dir = os.path.dirname(manifest_path)
    heatmaps_dir = args.output_dir
    try:
        os.mkdir(heatmaps_dir)
    except OSError:
        pass

    heatmap_area = args.area
    depth = args.depth
    threshold = args.threshold

    with open(manifest_path, 'r') as in_file:
        manifest = json.load(in_file)

        # Copy manifest
        tile_manifest = copy.deepcopy(manifest)
        tile_manifest["frames"] = []

        framelist = []

        if args.frame:
            framelist.append(manifest["frames"][args.frame])
        else:
            framelist = manifest["frames"]
        
        for frame in framelist:
            tiles = tiles_from_heatmap(frame, heatmap_area, depth, threshold, manifest["kick_flags"], manifest_dir, heatmaps_dir)
            tiled_frame = add_tiles_to_frame(tiles, copy.deepcopy(frame))
            tile_manifest["frames"].append(tiled_frame)

        return json.dumps(tile_manifest, indent=False, sort_keys=True)
