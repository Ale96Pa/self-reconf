"""The coordinator depends indireclty on PBFT because it launches availability.py"""
import subprocess
import time
import json
import redis
from pathlib import Path
import csv

REDIS_HOST = "192.168.1.189"
REDIS_PORT = 6379
STREAM_KEY = "aggregated_metrics_stream"
AVAILABILITY_PERCENT_STREAM = "availability_percent_stream"

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

coordinator_dir = Path(__file__).resolve().parent
metrics_dir = coordinator_dir / "metrics"

#start the two monitoring scripts
monitor_process = subprocess.Popen(["python", str(metrics_dir / "availability.py")])
risk_process = subprocess.Popen(["python", str(metrics_dir / "risk.py")])
ttc_process = subprocess.Popen(["python", str(metrics_dir / "ttc.py")])

print("Availability monitor e Risk Calculator avviati!")

try:
    while True:
        time.sleep(10)  #each 10 sec aggregate data

        #read the results from the files generated from the two scripts
        availability_file_1 = coordinator_dir / "availability_results_counters.json"
        availability_file_2 = coordinator_dir / "availability_times.csv"
        ttr_file = coordinator_dir / "ttr_times.csv"
        risk_file = metrics_dir / "device_risks.csv"
        ttc_file = metrics_dir / "ttc.csv"

        data_availability_percent = {}
        aggregated_data = {}

        #availability
        if availability_file_1.exists():
            with open(availability_file_1, "r") as f:
                data_availability_percent["availability"] = json.load(f)

        if availability_file_2.exists():
            times_list = []
            with open(availability_file_2, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    times_list.append(row)
                    aggregated_data["availability_times"] = times_list

        if ttr_file.exists():
            ttr_list = []
            with open(ttr_file, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    ttr_list.append(row)
                    aggregated_data["ttr"] = ttr_list

        #risk
        if risk_file.exists():
            device_risks = []
            with open(risk_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    device_risks.append(row)
            aggregated_data["device_risks"] = device_risks

        #TTC
        if ttc_file.exists():
            device_ttc = []
            with open(ttc_file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    device_ttc.append(row)
        
        if device_risks and device_ttc:
            for risk_row in aggregated_data["device_risks"]:
                ttc_row = next((d for d in device_ttc if d["Device"] == risk_row["Device"]), None)
                if ttc_row:
                    risk_row["TTC"] = float(ttc_row["TTC"])

        

        # print the aggregated data for verification
        print("\nAggregated data to publish on first stream:")
        print(json.dumps(aggregated_data, indent=2))

        print("\nAggregated availability percent to publish on the availability stream:")
        print(json.dumps(data_availability_percent, indent=2))
        #writing on Redis stream
        r.xadd(STREAM_KEY, {"data": json.dumps(aggregated_data)})
        r.xadd(AVAILABILITY_PERCENT_STREAM, {"data": json.dumps(data_availability_percent)})
        print("Published aggregated data to Redis streams")

except KeyboardInterrupt:
    print("Stopping coordinator...")
    monitor_process.terminate()
    risk_process.terminate()
