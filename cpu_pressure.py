#!/usr/bin/env python3

import os
import json
from gzip import WRITE

from dateutil import parser
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
sentinel_time = parser.parse("2024-11-07T00:00:00+00:00")
bad_nodes = ["aks-user2-33946009-vmss000000", "aks-user1-17939295-vmss000005", "aks-user3-35933842-vmss000005", "aks-user3-35933842-vmss000002", "aks-user3-35933842-vmss000003"]
plasma = matplotlib.colormaps.get_cmap('plasma')

all_nodes = []
for root, dirs, files in os.walk("_output/data"):
    for filename in files:
        node = os.path.splitext(filename)[0]
        all_nodes.append(node)

node_colors = {}
good_nodes = [node for node in all_nodes if node not in bad_nodes]
for idx, node in enumerate(good_nodes):
    node_colors[node] = plasma(0.33 * (float(idx)/len(good_nodes)))
for idx, node in enumerate(bad_nodes):
    node_colors[node] = plasma(0.66 + 0.33 * (float(idx)/len(bad_nodes)))

rows = 10
fig, axs = plt.subplots(rows, 1, sharex=True, figsize=(150, rows * 9))
kubelet = axs[0]
containerd = axs[1]
kubepods = axs[2]
system = axs[3]
cpu_user = axs[4]
cpu_nice = axs[5]
cpu_system = axs[6]
mem_used = axs[7]
mem_swap = axs[8]
disk_ios = axs[9]
nodes = []
for root, dirs, files in os.walk("_output/data"):
    for filename in files:
        node = os.path.splitext(filename)[0]
        with open(os.path.join(root, filename), "r") as f:
            data = json.load(f)
            cpu_pressure_full = {}

            for key in data:
                time = parser.parse(key)

                if "cgroups" in data[key]:
                    for cgroup in data[key]["cgroups"]:
                        if "cpu.pressure" in data[key]["cgroups"][cgroup]:
                            pressure = data[key]["cgroups"][cgroup]["cpu.pressure"]
                            for line in pressure:
                                if line.startswith("full"):
                                    infos = line.split(" ")
                                    if len(infos) == 5:
                                        parts = infos[1].split("=")
                                        if len(parts) == 2 and parts[0] == "avg10":
                                            if cgroup not in cpu_pressure_full:
                                                cpu_pressure_full[cgroup] = {"date": [], "value": []}
                                            cpu_pressure_full[cgroup]["date"].append(time)
                                            cpu_pressure_full[cgroup]["value"].append(float(parts[1]))
                                        else:
                                            print("found part with incorrect label: " + infos[1])
                                    else:
                                        print("found incorrect number of infos: " + line)

                if "cgroups" in data[key] and "system.slice" in data[key]["cgroups"] and "children" in data[key]["cgroups"]["system.slice"]:
                    for cgroup in data[key]["cgroups"]["system.slice"]["children"]:
                        if "cpu.pressure" in data[key]["cgroups"]["system.slice"]["children"][cgroup]:
                            pressure = data[key]["cgroups"]["system.slice"]["children"][cgroup]["cpu.pressure"]
                            for line in pressure:
                                # https://docs.kernel.org/accounting/psi.html#pressure-interface
                                # full avg10=0.00 avg60=0.00 avg300=0.00 total=0
                                if line.startswith("full"):
                                    infos = line.split(" ")
                                    if len(infos) == 5:
                                        parts = infos[1].split("=")
                                        if len(parts) == 2 and parts[0] == "avg10":
                                            if cgroup not in cpu_pressure_full:
                                                cpu_pressure_full[cgroup] = {"date": [], "value": []}
                                            cpu_pressure_full[cgroup]["date"].append(time)
                                            cpu_pressure_full[cgroup]["value"].append(float(parts[1]))
                                        else:
                                            print("found part with incorrect label: " + infos[1])
                                    else:
                                        print("found incorrect number of infos: " + line)

            units = {
                "containerd.service": containerd,
                "kubelet.service": kubelet,
                "system.slice": system,
                "kubepods.slice": kubepods,
            }
            for unit in units:
                if unit not in cpu_pressure_full:
                    continue

                df = pd.DataFrame(cpu_pressure_full[unit])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)

                # print(f"{node}: {unit}: {df["value"].max()}")

                units[unit].plot(df.index, df["value"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)

            cpu_usage = {}
            for key in data:
                time = parser.parse(key)

                # https://www.kernel.org/doc/html/latest/filesystems/proc.html#miscellaneous-kernel-statistics-in-proc-stat
                # cpu  2083288 187  326416 16266106 17501  36640 35408   0     0     0
                #      user    nice system idle     iowait irq   softirq steal guest guest_nice
                # Units are USER_HZ, which is 1/100s
                if "cpu" in data[key]:
                    cpu = data[key]["cpu"]
                    for line in cpu:
                        parts = line.split()
                        if len(parts) < 4:
                            continue
                        if parts[0] == "cpu":
                            cpu_labels = {
                                "user": 1,
                                "nice": 2,
                                "system": 3,
                            }
                            for cpu_label in cpu_labels:
                                if cpu_label not in cpu_usage:
                                    cpu_usage[cpu_label] = {"date": [], "value": []}
                                cpu_usage[cpu_label]["date"].append(time)
                                cpu_usage[cpu_label]["value"].append(float(parts[cpu_labels[cpu_label]]))

            memory_labels = {
                "total": "MemTotal:",
                "available": "MemAvailable:",
                "swap_free": "SwapFree:",
                "swap_total": "SwapTotal:",
            }
            memory_usage = {"date": []}
            for key in memory_labels:
                memory_usage[key] = []

            for key in data:
                time = parser.parse(key)

                # https://www.kernel.org/doc/html/latest/filesystems/proc.html#meminfo
                # MemTotal:       32858820 kB
                # MemAvailable:   27214312 kB
                if "mem" in data[key]:
                    mem = data[key]["mem"]
                    found = False
                    for line in mem:
                        parts = line.split()
                        if len(parts) < 3:
                            continue

                        for memory_label in memory_labels:
                            if parts[0] == memory_labels[memory_label]:
                                if parts[2] != "kB":
                                    print(f"found unknown memory unit {parts[2]}")
                                    continue
                                found = True
                                memory_usage[memory_label].append(int(parts[1]))

                    if found:
                        memory_usage["date"].append(time)

            disk_usage = {}
            for key in data:
                time = parser.parse(key)
                # https://www.kernel.org/doc/Documentation/block/stat.txt

                if "blocks" in data[key]:
                    for block in data[key]["blocks"]:
                        if block not in disk_usage:
                            disk_usage[block] = {"date": [], "ios": [], "inflight": []}
                        for line in data[key]["blocks"][block]:
                            parts = line.split()
                            if len(parts) < 17:
                                continue
                            read_ios = int(parts[0])
                            write_ios = int(parts[4])
                            discard_ios = int(parts[11])
                            inflight_ios = int(parts[8])
                            disk_usage[block]["date"].append(time)
                            disk_usage[block]["ios"].append(read_ios + write_ios + discard_ios)
                            disk_usage[block]["inflight"].append(inflight_ios)

            for block in disk_usage:
                df = pd.DataFrame(disk_usage[block])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df['rate'] = (df['ios'].diff() / df.index.to_series().diff().dt.total_seconds())

                disk_ios.plot(df.index, df["rate"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)

            modes = {
                "user": cpu_user,
                "nice": cpu_nice,
                "system": cpu_system,
            }
            for mode in modes:
                if mode not in cpu_usage:
                    continue

                df = pd.DataFrame(cpu_usage[mode])
                df['date'] = pd.to_datetime(df['date'])
                df.set_index('date', inplace=True)
                df['rate'] = (df['value'].diff() / df.index.to_series().diff().dt.total_seconds()) / (16 * 100 / 100) # divide by 100 for USER_HZ->seconds, by 16 for % CPU, multiply by 100 for 0-100% range

                modes[mode].plot(df.index, df["rate"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)

            df = pd.DataFrame(memory_usage)
            df['date'] = pd.to_datetime(df['date'])
            df.set_index('date', inplace=True)
            df['mem_used'] = 100 * (1 - df['available'] / df['total'])
            df['swap_used'] = 100 * ((df['swap_total'] - df['swap_free']) / df['swap_total'])

            mem_used.plot(df.index, df["mem_used"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)
            mem_swap.plot(df.index, df["swap_used"], color=node_colors[node],zorder=100 if node in bad_nodes else 0)


start = parser.parse("2024-11-08T23:00:00+00:00")
end = parser.parse("2024-11-09T00:30:00+00:00")

plt.legend(nodes)
pressures = {
    'kubelet': kubelet,
    'containerd': containerd,
    'kubepods.slice': kubepods,
    'system.slice': system,
}
for title in pressures:
    pressures[title].title.set_text(title)
    pressures[title].set(ylabel='Full CPU Pressure (%)')
    pressures[title].set_ylim([0,60])
    pressures[title].set_xlim([start,end])

usages = {
    'user': cpu_user,
    'nice': cpu_nice,
    'system': cpu_system,
}
for title in usages:
    usages[title].title.set_text(title)
    usages[title].set(ylabel='CPU Usage (%)')
    usages[title].set_ylim([0,100])
    usages[title].set_xlim([start,end])

memories = {
    'used': mem_used,
    'swap': mem_swap
}
for title in memories:
    memories[title].title.set_text(title)
    memories[title].set(ylabel='Memory Fraction (%)')
    memories[title].set_ylim([0,100])
    memories[title].set_xlim([start,end])

disk_ios.title.set_text('Disk I/Os')
disk_ios.set(ylabel='IOPS')
disk_ios.set_xlim([start,end])

plt.xlabel('Date')
plt.show()
