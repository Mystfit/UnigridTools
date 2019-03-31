try:
    import OpenImageIO as oiio
except ImportError:
    from oiio import OpenImageIO as oiio
import os
import json
import sys

try:
    import Queue as queue
except ImportError:
    import queue

import time
import threading

if len(sys.argv) < 4:
    print("Missing arguments. Script requires manifest_path, tiles_path, images_path")
    sys.exit()

manifest_path = sys.argv[1]
tiles_path = sys.argv[2]
images_path = sys.argv[3]
num_worker_threads = int(sys.argv[4])
stitch_queue = queue.Queue()


def frame_thread():
    frame = None
    try:
        frame = stitch_queue.get_nowait()
    except queue.Empty:
        pass

    while frame:
        frame_path = str(os.path.join(images_path, frame["outfile"]))
        print("Assembling frame {}".format(frame_path))

        first_tile_path = str(os.path.join(tiles_path, frame["tiles"][0]["outfile"]))
        print(first_tile_path)
        if not os.path.isfile(first_tile_path):
            continue

        first_tile = oiio.ImageBuf(first_tile_path)
        spec = first_tile.spec()
        frame_buf = oiio.ImageBuf(oiio.ImageSpec(frame["res_x"], frame["res_y"], spec.nchannels, spec.format))

        for tile in frame["tiles"]:
            tile_path = str(os.path.join(tiles_path, tile["outfile"]))
            if not os.path.isfile(tile_path):
                continue
            tile_buf = oiio.ImageBuf(tile_path)

            oiio.ImageBufAlgo.paste(frame_buf, tile["coords"][0], tile["coords"][1], 0, 0, tile_buf)
        
        print("Writing {}".format(frame_path))
        frame_buf.write(frame_path)

        try:
            frame = stitch_queue.get_nowait()
        except queue.Empty:
            break


with open(manifest_path, 'r') as f:
    manifest = json.loads(f.read())

    for frame in manifest["frames"]:
        stitch_queue.put(frame)

    for thread in range(num_worker_threads):
        print("Creating worker thread")
        t = threading.Thread(target=frame_thread)
        t.start()

    while not stitch_queue.empty():
        time.sleep(1)

    print("Done")
