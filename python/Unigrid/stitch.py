try:
    import OpenImageIO as oiio
except ImportError:
    from oiio import OpenImageIO as oiio
import os
import platform
import json
import sys
import multiprocessing
import argparse

try:
    import Queue as queue
except ImportError:
    import queue

import time
import threading
from pathlib import Path


class Stitcher(object):
    def __init__(self, num_worker_threads):
        self.stitch_queue = queue.Queue()
        self.threads = []
        self.num_worker_threads = num_worker_threads

    def frame_thread(self):
        stitch_args = None
        try:
            stitch_args = self.stitch_queue.get_nowait()
        except queue.Empty:
            pass

        while stitch_args:
            frame = stitch_args[0]
            tiles_path = Path(stitch_args[1])
            images_path = Path(stitch_args[2])
            frame_path = str(os.path.join(images_path, frame["outfile"]))
            print("Assembling frame {}".format(frame_path))

            first_tile_path = os.path.join(tiles_path, frame["tiles"][0]["outfile"])
            if os.path.isfile(first_tile_path):
                first_tile = oiio.ImageBuf(str(first_tile_path))
                spec = first_tile.spec()
                frame_buf = oiio.ImageBuf(oiio.ImageSpec(frame["res_x"], frame["res_y"], spec.nchannels, spec.format))

                for tile in frame["tiles"]:
                    tile_path = os.path.join(tiles_path, tile["outfile"])
                    if not os.path.isfile(tile_path):
                        continue
                    tile_buf = oiio.ImageBuf(str(tile_path))

                    oiio.ImageBufAlgo.paste(frame_buf, tile["coords"][0], tile["coords"][1], 0, 0, tile_buf)
                
                print("Writing {}".format(frame_path))

                try:
                    os.mkdir(os.path.dirname(frame_path))
                except FileExistsError:
                    pass
                frame_buf.write(str(frame_path))
            else:
                print("Could not find first tile. Aborting frame stitch")
            
            try:
                stitch_args = self.stitch_queue.get_nowait()
            except queue.Empty:
                print("Worker exiting")
                break

    def stitch(self, manifest_path, tiles_path, images_path):
        with open(Path(manifest_path).resolve(), 'r') as f:
            manifest = json.loads(f.read())

            for frame in manifest["frames"]:
                self.stitch_queue.put((frame, tiles_path, images_path))

            for thread in range(self.num_worker_threads):
                print("Creating worker thread")
                t = threading.Thread(target=self.frame_thread)
                self.threads.append(t)
                t.start()

            try:
                while not self.stitch_queue.empty():
                    time.sleep(1)
            except KeyboardInterrupt:
                pass

            print("Waiting for workers to finish...")


def run_stitcher():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', help='Input manifest file')
    parser.add_argument('-i', '--input-tiles', required=True, default=None, type=str, help='Directory containing input tiles to stitch')
    parser.add_argument('-o', '--output-images', required=True, default=None, type=str, help='Directory output images will be saved to')
    parser.add_argument('-t', '--threads', default=multiprocessing.cpu_count(), type=int, help='Number of threads for stitching frames (1 frame per thread)')

    args = parser.parse_args()
    stitcher = Stitcher(args.threads)
    stitcher.stitch(args.manifest, args.input_tiles, args.output_images)


if __name__ == "__main__":
    if len(sys.argv) < 4:
        message_str = ""
        for arg in sys.argv:
            message_str += "{},\n".format(arg) 
        print("Missing arguments. Script requires manifest_path, tiles_path, images_path. Received: {}".format(message_str))
        sys.exit(1)

    manifest_path = sys.argv[1]
    tiles_path = sys.argv[2]
    images_path = sys.argv[3]
    num_worker_threads = int(sys.argv[4])
    stitcher = Stitcher(num_worker_threads)
    stitcher.run_stitcher(manifest_path, tiles_path, images_path)
