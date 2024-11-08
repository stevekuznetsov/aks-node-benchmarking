#!/usr/bin/env python3

import os
import json
from dateutil import parser
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
sentinel_time = parser.parse("2024-11-07T00:00:00+00:00")
bad_nodes = ["aks-user1-16576121-vmss00001g", "aks-user1-16576121-vmss00001i", "aks-user2-16576121-vmss00001a", "aks-user3-16576121-vmss00001b", "aks-user3-16576121-vmss00001f"]
plasma = matplotlib.colormaps.get_cmap('plasma')

all_nodes = []
for root, dirs, files in os.walk("/tmp/data"):
    for filename in files:
        node = os.path.splitext(filename)[0]
        all_nodes.append(node)

node_colors = {}
good_nodes = [node for node in all_nodes if node not in bad_nodes]
for idx, node in enumerate(good_nodes):
    node_colors[node] = plasma(0.33 * (float(idx)/len(good_nodes)))
for idx, node in enumerate(bad_nodes):
    node_colors[node] = plasma(0.66 + 0.33 * (float(idx)/len(bad_nodes)))

fig, axs = plt.subplots(6, 1, sharex=True, figsize=(150, 36))
kubelet = axs[0]
containerd = axs[1]
kubepods = axs[2]
system = axs[3]
total = axs[4]
weight = axs[5]
nodes = []
for root, dirs, files in os.walk("/tmp/data"):
    for filename in files:
        node = os.path.splitext(filename)[0]
        with open(os.path.join(root, filename), "r") as f:
            data = json.load(f)
            times = []
            for key in data:
                if key == "name":
                    continue
                times.append(parser.parse(key))
            times.sort()
            raw = {
                'date': [sentinel_time + (time - times[0]) for time in times],
            }
            units = ["containerd.service", "kubelet.service"]
            for unit in units:
                values = []
                for time in times:
                    value = None
                    if time.isoformat() not in data:
                        values.append(value)
                        continue
                    if "cgroups" not in data[time.isoformat()]:
                        values.append(value)
                        continue
                    if "system.slice" not in data[time.isoformat()]["cgroups"]:
                        values.append(value)
                        continue
                    if "children" not in data[time.isoformat()]["cgroups"]["system.slice"]:
                        values.append(value)
                        continue
                    if unit not in data[time.isoformat()]["cgroups"]["system.slice"]["children"]:
                        values.append(value)
                        continue
                    if "cpu.pressure" not in data[time.isoformat()]["cgroups"]["system.slice"]["children"][unit]:
                        values.append(value)
                        continue
                    pressure = data[time.isoformat()]["cgroups"]["system.slice"]["children"][unit]["cpu.pressure"]
                    for line in pressure:
                        if line.startswith("full"):
                            infos = line.split(" ")
                            if len(infos) == 5:
                                parts = infos[1].split("=")
                                if len(parts) == 2 and parts[0] == "avg10":
                                    value = float(parts[1])
                                else:
                                    print("found part with incorrect label: " + infos[1])
                            else:
                                print("found incorrect number of infos: " + line)
                    values.append(value)
                raw[unit] = values

            weights = []
            for time in times:
                value = None
                if time.isoformat() not in data:
                    weights.append(value)
                    continue
                weights.append(int(data[time.isoformat()]["kubepods.slice_weight"]))
            raw["weight"] = weights

            df = pd.DataFrame(raw)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)

            kubelet.plot(df.index, df["kubelet.service"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)
            containerd.plot(df.index, df["containerd.service"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)
            weight.plot(df.index, df["weight"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)

            sliceraw = {
                'date': [sentinel_time + (time - times[0]) for time in times],
            }
            slices = ["kubepods.slice", "system.slice"]
            for slice in slices:
                values = []
                for time in times:
                    value = None
                    if time.isoformat() not in data:
                        values.append(value)
                        continue
                    if "cgroups" not in data[time.isoformat()]:
                        values.append(value)
                        continue
                    if slice not in data[time.isoformat()]["cgroups"]:
                        values.append(value)
                        continue
                    if "cpu.stat" not in data[time.isoformat()]["cgroups"][slice]:
                        values.append(value)
                        continue
                    pressure = data[time.isoformat()]["cgroups"][slice]["cpu.stat"]
                    for line in pressure:
                        if line.startswith("usage_usec"):
                            infos = line.split(" ")
                            if len(infos) == 2:
                                value = int(infos[1])
                            else:
                                print("found incorrect number of cpu.stat infos: " + line)
                    values.append(value)
                sliceraw[slice] = values

            totals = []
            for time in times:
                value = None
                if time.isoformat() not in data:
                    totals.append(value)
                    continue
                if "cgroups" not in data[time.isoformat()]:
                    totals.append(value)
                    continue

                for slice in data[time.isoformat()]["cgroups"]:
                    if "cpu.stat" not in data[time.isoformat()]["cgroups"][slice]:
                        continue
                    pressure = data[time.isoformat()]["cgroups"][slice]["cpu.stat"]
                    for line in pressure:
                        if line.startswith("usage_usec"):
                            infos = line.split(" ")
                            if len(infos) == 2:
                                if value is None:
                                    value = int(infos[1])
                                else:
                                    value += int(infos[1])
                            else:
                                print("found incorrect number of cpu.stat infos: " + line)
                totals.append(value)
            sliceraw['total'] = totals

            df2 = pd.DataFrame(sliceraw)
            df2['date'] = pd.to_datetime(df2['date'])
            df2.set_index('date', inplace=True)
            df2['kubepods.rate'] = df2['kubepods.slice'].diff() / df2.index.to_series().diff().dt.total_seconds()
            df2['system.rate'] = df2['system.slice'].diff() / df2.index.to_series().diff().dt.total_seconds()
            df2['total.rate'] = df2['total'].diff() / df2.index.to_series().diff().dt.total_seconds()

            kubepods.plot(df2.index, df2["kubepods.rate"] / 1e6, color=node_colors[node],zorder=100 if node in bad_nodes else 0)
            system.plot(df2.index, df2["system.rate"] / 1e6, color=node_colors[node],zorder=100 if node in bad_nodes else 0)
            total.plot(df2.index, df2["total.rate"] / 1e6, color=node_colors[node],zorder=100 if node in bad_nodes else 0)

plt.legend(nodes)
kubelet.title.set_text('kubelet')
kubelet.set(ylabel='Full CPU Pressure (%)')
containerd.title.set_text('containerd')
containerd.set(ylabel='Full CPU Pressure (%)')
kubepods.title.set_text('kubepods.slice')
kubepods.set(ylabel='CPU Usage (seconds)')
system.title.set_text('system.slice')
system.set(ylabel='CPU Usage (seconds)')
total.title.set_text('total')
total.set(ylabel='CPU Usage (seconds)')
weight.title.set_text('kubepods.slice cpu.weight')
weight.set(ylabel='CPU Weight')
plt.xlabel('Date')
plt.show()
