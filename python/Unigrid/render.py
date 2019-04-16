import os
import sys
import json
import math
import argparse

from subprocess import call

# Build a kick string command from flags and tokens
def build_kick_command(kick, flags, token_values):
    command = kick
    for flag, val in flags.items():
        if isinstance(val, dict):
            for subkey, subval in val.items():
                command += " -{} {} {}".format(flag, subkey, subval)
        else:
            command += " -" + flag
            if len(val):
                command += " " + val
    for token, value in token_values.items():
        command = command.replace(token, value) 
    return command

def render(kick, frame, flags, ass_files, project_path, destination):
    # Per file token replacements
    token_values = {
        "<PROJECT_PATH>": project_path,
        "<OUT_FILE>": destination,
        "<IN_FILE>": " ".join(ass_files)
    }

    try:
        os.makedirs(os.path.dirname(destination))
    except OSError:
        pass

    command = build_kick_command(kick, flags, token_values)
    call(command.split(" "))

def render_heatmaps(kick_cmd, frame, area, flags, maniest_dir, destination):
    # Calculate resized heatmap size using total area
    aspect = float(frame["res_x"]) / float(frame["res_y"])
    height = math.sqrt(area / aspect)
    width = height * aspect
    print("Heatmap Aspect: {} Width: {} Height: {}".format(aspect, width, height))

    heatmap_frame_path = str(os.path.join(destination, frame["outfile"]))
    ass_files = [os.path.normpath(os.path.join(maniest_dir, ass_scene)) for ass_scene in frame["resources"]]

    # Render cpu tilemaps
    flags["set"]["options.xres"] = math.floor(width)
    flags["set"]["options.yres"] = math.floor(height)
    render(kick_cmd, frame, flags, ass_files, maniest_dir, heatmap_frame_path)

def run_render_heatmaps():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', help='Input manifest file')
    parser.add_argument('-kc', '--kick-cmd', default="kick", type=str, help='Kick command')
    parser.add_argument('-f', '--frame', default=None, type=int, help='Frame to render')
    parser.add_argument('-o', '--output-dir', default=os.path.join(os.getcwd(), "heatmaps"), help='Output heatmap dir')
    parser.add_argument('-a', '--area', default=10000, type=int, help='Area of heatmap')
    args = parser.parse_args()

    manifest_path = args.manifest
    manifest_dir = os.path.dirname(manifest_path)
    heatmaps_dir = args.output_dir
    try:
        os.mkdir(heatmaps_dir)
    except OSError:
        pass

    with open(manifest_path, 'r') as in_file:
        manifest = json.load(in_file)
        framelist = []

        if args.frame:
            framelist.append(manifest["frames"][args.frame])
        else:
            framelist = manifest["frames"]
        
        for frame in framelist:
            render_heatmaps(args.kick_cmd, frame, args.area, manifest["kick_flags"], manifest_dir, args.output_dir)
