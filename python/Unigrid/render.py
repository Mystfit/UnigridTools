import os
import sys
import json
import math
from pathlib import Path
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


def render_frame_heatmap(kick, frame, width, height, flags, source, destination):
    flags["set"]["options.xres"] = math.floor(width)
    flags["set"]["options.yres"] = math.floor(height)
    render(kick, frame, flags, source, destination)

def render(kick, frame, flags, source, destination):
    resources = [os.path.normpath(os.path.join(source, resource)) for resource in frame["resources"]]

    # Per file token replacements
    token_values = {
        "<PROJECT_PATH>": source,
        "<OUT_FILE>": str(Path(destination).resolve()),
        "<IN_FILE>": " ".join(resources)
    }

    try:
        os.makedirs(os.path.dirname(destination))
    except OSError:
        pass

    command = build_kick_command(kick, flags, token_values)
    call(command.split(" "))
