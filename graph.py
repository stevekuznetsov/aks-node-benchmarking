#!/usr/bin/env python3

import os
from dateutil import parser
import json

# Input file format:
# n.b. the '===' separators were from a previous run where dates spanned files, now ignored
#
# preamble ...
# == START ==
# <date stamp>
# /absolute/path/to/file
# <file contents>
# ---
# <date stamp>
# /absolute/path/to/file
# <file contents>
# ---
# ===
# <date stamp>
# /absolute/path/to/file
# <file contents>
# ---
# <date stamp>
# /absolute/path/to/file
# <file contents>
# ---
# ===

os.makedirs("_output/data", exist_ok=True)

for root, dirs, files in os.walk("_output/logs"):
    for filename in files:
        path = os.path.join(root, filename)
        node = os.path.basename(os.path.dirname(path))
        output = f"_output/data/{node}.json"
        if os.path.exists("_output/data/" + node + ".json"):
            print(f"{node}: already processed to {output}")
            continue
        node_data = {}
        with open(path, 'r') as raw:
            all = raw.read()
            topLevel = all.split('== START ==')
            starting_index = 0
            # if we were not able to get the very beginning of the logs for the pod,
            # we will end up in the middle of some file, which we will need to ignore
            if len(topLevel) != 2:
                print("did not find start in file " + filename)
                starting_index = 1
            else:
                all = topLevel[1]
            chunks = all.split('===\n')
            print(f"{node}: found {len(chunks)} chunks")
            for chunkIdx, chunk in enumerate(chunks):
                if chunkIdx % int(len(chunks) / 20) == 0 and chunkIdx != 0:
                    print(f"{node}: processed {chunkIdx}/{len(chunks)} chunks")
                if chunkIdx <= starting_index:
                    continue
                files = chunk.split('\n---\n')
                # print(f"{node}: found {len(files)} files")
                for fileIdx, file in enumerate(files):
                    # if fileIdx % int(len(files) / 20) == 0 and fileIdx != 0:
                    #     print(f"{node}: chunk {chunkIdx}: processed {fileIdx}/{len(files)} files")
                    if file == "":
                        continue
                    lines = file.split('\n')
                    if len(lines) < 3:
                        continue
                    if lines[0] == "":
                        continue

                    # sometimes the `cat` fails and somehow the output from the shell script is out of order,
                    # so the error message invades the next file block after the '---' separator
                    # TODO: sometimes it's in another position, so we should make this remove the line from wherever it is
                    if "No such file or directory" in lines[0]:
                        lines = lines[1:]

                    time = None
                    try:
                        time = parser.parse(lines[0])
                    except Exception as e:
                        print(f"{node}: {chunkIdx}: {fileIdx}: failed to parse time: {e}")

                    if time is None:
                        continue

                    if time.isoformat() not in node_data:
                        node_data[time.isoformat()] = {'cpu': [], 'mem': [], 'disk': [], 'cgroups': {}, 'blocks': {}}

                    special_cases = {
                        "/proc/stat": "cpu",
                        "/proc/meminfo": "mem",
                        "/proc/diskstats": "disk"
                    }
                    special = False
                    for name in special_cases:
                        if lines[1].strip() == name:
                            node_data[time.isoformat()][special_cases[name]] = lines[2:]
                            special = True

                    if special:
                        continue

                    if lines[1].strip().startswith("/sys/block"):
                        # /sys/block/loop3/stat
                        pathparts = os.path.relpath(lines[1], start="/sys/block").split(os.sep)
                        if len(pathparts) == 2 and pathparts[1] == "stat":
                            node_data[time.isoformat()]['blocks'][pathparts[0]] = lines[2:]
                        continue

                    pathparts = os.path.relpath(lines[1], start="/sys/fs/cgroup").split(os.sep)
                    if len(pathparts) == 2:
                        if pathparts[0] not in node_data[time.isoformat()]['cgroups']:
                            node_data[time.isoformat()]['cgroups'][pathparts[0]] = {}
                        node_data[time.isoformat()]['cgroups'][pathparts[0]][pathparts[1]] = lines[2:]
                    if len(pathparts) == 3:
                        if pathparts[0] not in node_data[time.isoformat()]['cgroups']:
                            node_data[time.isoformat()]['cgroups'][pathparts[0]] = {}
                        if "children" not in node_data[time.isoformat()]['cgroups'][pathparts[0]]:
                            node_data[time.isoformat()]['cgroups'][pathparts[0]]["children"] = {}
                        if pathparts[1] not in node_data[time.isoformat()]['cgroups'][pathparts[0]]["children"]:
                            node_data[time.isoformat()]['cgroups'][pathparts[0]]["children"][pathparts[1]] = {}
                        node_data[time.isoformat()]['cgroups'][pathparts[0]]["children"][pathparts[1]][pathparts[2]] = lines[2:]

            with open(output, "w") as out:
                try:
                    json.dump(node_data, out)
                    print(f"{node}: wrote to output {output}")
                    break
                except Exception as e:
                    print(f"{node}: failed to write to output: {e}")
