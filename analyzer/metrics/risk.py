import json
from collections import defaultdict
from pathlib import Path
import csv
import sys

compute_for_candidates = True

if compute_for_candidates:
    json_filename = "MyCandidatesPath.json"
    devices = [f"192.168.56.{i}" for i in range(50,62)]
else:
    json_filename = "MyNetworkPath.json"
    devices = [f"192.168.56.{i}" for i in range(110,119)]

#build the path to the JSON file

# build the path to the JSON file
dir = Path(__file__).resolve().parent  # .../Thesis project/analyzer/metrics
json_path = dir.parents[1] / "monitor" / "ag-basics" / json_filename  
# -> .../Thesis project/monitor/ag-basics/MyNetworkPath.json

#check if the file exists
if not json_path.exists():
    print(f"Error: JSON file '{json_path}' does not exist.")
    sys.exit(1)

#load the JSON file
with json_path.open("r", encoding="utf-8") as f:
    data = json.load(f)


#intialize the risk dictionary to track max risk per device
device_max_risk = {dev: 0.0 for dev in devices}

# collect all risks per device for average calculation
device_risks_list = defaultdict(list)

# initializing a counter of path for each device (dictionary initialized to 0)
device_path_count = {dev: 0 for dev in devices}

#Each path has an overall risk. Each node in the path represents a device.
#If a device appears in the path, the path’s risk is assigned to that device.

for entry in data.get("paths", []):
    #risk associated to this path
    risk = float(entry.get("risk",0))
    #list of nodes in this path
    path_nodes = entry.get("path",[])
    #iterate over each node in the path
    for node in path_nodes:
        #check if the node is one of the devices of our network
        for dev in devices:
            #if the device is in the node, check if the risk is higher than current max
            if dev in node:
                if risk > device_max_risk[dev]:
                    device_max_risk[dev] = risk
                #collect risk for average calculation
                device_risks_list[dev].append(risk)
                #count the number of paths for this device
                device_path_count[dev] += 1

# calculate average risk per device
device_avg_risk = {}
for dev in devices:
    risks = device_risks_list.get(dev, [])
    if risks:
        avg_risk = sum(risks) / len(risks)
    else:
        avg_risk = 0.0
    device_avg_risk[dev] = avg_risk

#print the results
print("\n Maximum risk for device:")

for dev in devices:
    print(f"{dev} -> max risk = {device_max_risk[dev]}")

print("\nAverage risk for device:")
for dev in devices:
    print(f"{dev} -> avg risk = {device_avg_risk[dev]:.6f}")

print("\nNumber of paths for device:")
for dev in devices:
    print(f"{dev} -> num paths = {device_path_count[dev]}")

if compute_for_candidates:
    cvs_path = dir / "candidate_risks.csv"
else:
    cvs_path = dir / "device_risks.csv"
    
with cvs_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Device", "Max Risk", "Avg Risk", "Num Paths"])
    for dev in devices:
        writer.writerow([dev, device_max_risk[dev], f"{device_avg_risk[dev]:.6f}", device_path_count[dev]])

print(f"\nResults saved to '{cvs_path}'")
