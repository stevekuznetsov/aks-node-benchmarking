#!/usr/bin/env python3

import os
from dateutil import parser
import json

# time: {
#   node: {
#       kubepods.slice_weight: 123,
#       cgroups: {
#           system.slice: {
#               cpu.stat: "",
#               cpu.pressure: "",
#               memory.stat: "",
#               memory.pressure: "",
#               kubelet.slice: {
#                   cpu.stat: "",
#                   cpu.pressure: "",
#                   memory.stat: "",
#                   memory.pressure: "",
#               }
#       }
# }
data = {}

for root, dirs, files in os.walk("/tmp/logs"):
    for filename in files:
        path = os.path.join(root, filename)
        node = os.path.basename(os.path.dirname(path))
        if os.path.exists("/tmp/data/" + node + ".json"):
            print(node + " already processed to " + "/tmp/data/" + node + ".json")
            continue
        node_data = {
            "name": node
        }
        with open(path, 'r') as raw:
            all = raw.read()
            chunks = all.split('===\n')
            for chunk in chunks:
                lines = chunk.split('\n')
                if len(lines) == 0:
                    continue
                if lines[0].startswith("kube-reserved"):
                    lines = lines[1:]
                if lines[0] == "":
                    continue
                time = parser.parse(lines[0])
                print(node + "@" + lines[0])

                if time not in data:
                    node_data[time.isoformat()] = {}

                node_data[time.isoformat()] = {
                    "kubepods.slice_weight": lines[2]
                }
                lines = lines[3:] # TODO: 4: once we add --- after this one, or handle the first file special

                info = '\n'.join(lines)
                parts = info.split('---\n')

                cgroups = {}
                for part in parts:
                    if part == "":
                        continue
                    items = part.split('\n')
                    pathparts = os.path.relpath(items[0], start="/sys/fs/cgroup").split(os.sep)
                    if len(pathparts) == 2:
                        if pathparts[0] not in cgroups:
                            cgroups[pathparts[0]] = {}
                        cgroups[pathparts[0]][pathparts[1]] = items[1:]
                    if len(pathparts) == 3:
                        if pathparts[0] not in cgroups:
                            cgroups[pathparts[0]] = {}
                        if "children" not in cgroups[pathparts[0]]:
                            cgroups[pathparts[0]]["children"] = {}
                        if pathparts[1] not in cgroups[pathparts[0]]["children"]:
                            cgroups[pathparts[0]]["children"][pathparts[1]] = {}
                        cgroups[pathparts[0]]["children"][pathparts[1]][pathparts[2]] = items[1:]

                node_data[time.isoformat()]['cgroups'] = cgroups

            with open("/tmp/data/" + node + ".json", "w") as out:
                json.dump(node_data, out)

with open("/tmp/data.json", "w") as out:
    json.dump(data, out)