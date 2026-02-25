"""Some decision for availability are based on the PBFT protocol (the application running
on the evaluated system)
In this script some metrics are computed based on PBFT:
- availability_time (latency)
- availability percentage (based on the number of satisfied requests over total requests)
- a request is satisfied when a quorum of replies (2f+1) is received from replicas
"""

import redis
import time
import json
import os
import csv
import argparse
# this import is used to not overwrite files during benchmark
import datetime
#this import is used to not overwrite files during benchmark
ts_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

parser = argparse.ArgumentParser(description="Monitor availability from Redis")
parser.add_argument("--f", type=int, default=2, help="Number of tolerated Byzantine replicas")
parser.add_argument("--host", type=str, default="192.168.1.189", help="Redis host")
parser.add_argument("--port", type=int, default=6379, help="Redis port")
parser.add_argument("--outdir", type=str, default=".", help="Directory where to save output files")
args = parser.parse_args()

REDIS_HOST = args.host
REDIS_PORT = args.port
F = args.f  #number of byzantine
QUORUM = 2 * F + 1
TIMEOUT = 0.3  #seconds
OUT_DIR = args.outdir

os.makedirs(OUT_DIR, exist_ok=True)
#commented to not overwrite files during benchmark
#save_counters_file = os.path.join(OUT_DIR, "availability_results_counters.json")
#save_times_file = os.path.join(OUT_DIR, "availability_times.csv")
#save_ttr_file = os.path.join(OUT_DIR, "ttr_times.csv")

save_counters_file = os.path.join(OUT_DIR, f"availability_results_counters.json")
save_times_file = os.path.join(OUT_DIR, f"availability_times.csv")
save_ttr_file = os.path.join(OUT_DIR, f"ttr_times.csv")


#restore the counters if file exists
if os.path.exists(save_counters_file):
    with open(save_counters_file, "r") as f:
        state = json.load(f)
        total_requests = state["total_requests"]
        satisfied_requests = state["satisfied_requests"]
else:
    total_requests = 0
    satisfied_requests = 0

print(f"Starting with counters: {satisfied_requests}/{total_requests}")

#create CSV file with header if not exists (for the availability times)
if not os.path.exists(save_times_file):
    with open(save_times_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["t_start", "t_end", "availability_time", "value"])

#create CSV file with header if not exists (for the time to recover)
if not os.path.exists(save_ttr_file):
    with open(save_ttr_file, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["failure_start", "recovery_time", "ttr"])

#connect to Redis
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

#variables
t_start = None
reply_counts = {}
downtime_start = None #moment in which the failure starts
service_down = False #flag to indicate if the service is down

#new vars for "waiting for fifth reply"
fourth_reply_time = None
pending_value = None


#function to save counters in the file
def save_state():
    availability_percent = (satisfied_requests / total_requests * 100) if total_requests > 0 else 0
    with open(save_counters_file, "w") as f:
        json.dump({
            "total_requests": total_requests,
            "satisfied_requests": satisfied_requests,
            "availability_percent": availability_percent
        }, f)

print(f"Listening on Redis MONITOR to compute availability based on REPLY quorum ({QUORUM})...")

with r.monitor() as m:
    try:
        for raw in m.listen():
            line = str(raw["command"])
            ts = raw["time"]
            now = time.monotonic()

            #waiting for the fifth reply 
            #if the fith reply does not arrive, the system is considered down
            if fourth_reply_time is not None:
                if now - fourth_reply_time > TIMEOUT:
                    if reply_counts.get(pending_value, 0) < QUORUM:
                        print(f"Fifth reply missing for value={pending_value}, SYSTEM DOWN")
                        if not service_down:
                            downtime_start = now
                            service_down = True
                            print(f"SYSTEM DOWN - Failure started at {downtime_start}")
                    #reset waiting 
                    fourth_reply_time = None
                    pending_value = None


            #detect new request to replica-0 coming from the client
            if 'PUBLISH' in line and 'replica-0' in line and 'REQUEST' in line:
                t_start = ts
                reply_counts = {}
                total_requests += 1
                availability_percent = (satisfied_requests / total_requests * 100)
                print(f"[REQUEST] T_start = {t_start} (total_requests={total_requests})")
                print(f"Satisfied requests so far: {satisfied_requests}/{total_requests} ({availability_percent:.2f}%)")
                save_state()

            #detect REPLY to the client
            if '"REPLY"' in line and '"client-0"' in line and t_start is not None:
                start = line.find('{')
                end = line.rfind('}')
                if start != -1 and end != -1:
                    reply_str = line[start:end+1]
                    try:
                        reply_json = json.loads(reply_str)
                        value = reply_json.get("result")
                        #count the equal replies
                        reply_counts[value] = reply_counts.get(value, 0) + 1
                        count = reply_counts[value]
                        print(f"[REPLY] Value={value}, count={reply_counts[value]}")

                        if count == QUORUM - 1:
                            fourth_reply_time = now
                            pending_value = value
                            print(f"penultimate reply received for value={value}, waiting the last for {TIMEOUT}s...")

                        #check the quorum
                        if count >= QUORUM:
                            availability = ts - t_start #time of the last reply (2f+1) - time of the request
                            satisfied_requests += 1
                            print(f"Request SATISFIED! Value {value} reached quorum ({QUORUM}) in {availability:.6f}s")


                            #save to CSV the times
                            with open(save_times_file, "a", newline="") as f:
                                writer = csv.writer(f)
                                writer.writerow([t_start, ts, availability, value])

                            #check if service was DOWN -> RECOVERY
                            if service_down and downtime_start is not None:
                                ttr = now - downtime_start
                                print(f"[RECOVERY] Service recovered after {ttr:.6f}s")
                                with open(save_ttr_file, "a", newline="") as f:
                                    writer = csv.writer(f)
                                    writer.writerow([downtime_start, now, ttr])
                                service_down = False
                                downtime_start = None

                            #reset for next request
                            t_start = None
                            reply_counts = {}
                            fourth_reply_time = None
                            pending_value = None

                            availability_percent = (satisfied_requests / total_requests * 100) if total_requests > 0 else 0
                            print(f"Availability percentage: {satisfied_requests}/{total_requests} ({availability_percent:.2f}%)\n")
                            save_state()

                    except json.JSONDecodeError:
                        print(f"Cannot decode REPLY JSON: {reply_str}")

    except KeyboardInterrupt:
        print("\nStopped by the user. Saving state...")
        save_state()
        print("State saved. Exiting.")
