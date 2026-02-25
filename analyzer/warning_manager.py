"""
In this scripts some warnings depends on PBFT protocol behavior:
- availability warnings (if the number of active replicas is under the quorum 2f+1)
- latency warnings (if the average latency of last requests is over a threshold): the latency depends on PBFT message exchanges
- heartbeat warnings (based on the quorum)


"""
import redis
import json
import time
import threading
import tkinter as tk
from collections import deque
import os

#redis configuration
REDIS_HOST = "192.168.1.189"
REDIS_PORT = 6379
STREAM_KEY = "aggregated_metrics_stream"
HEARTBEAT_CHANNEL_PATTERN = "heartbeat"
AVAILABILITY_STREAM_KEY = "availability_percent_stream"


#period without heartbeat (in seconds) to consider a replica as failed
AVAILABILITY_THRESHOLD = 99.9  # percent
HEARTBEAT_TIMEOUT = 5
LATENCY_THRESHOLD = 0.3
TTC_threshold = 29  # days
F=2
QUORUM = 2*F +1
REPLICA_THRESHOLD = QUORUM +1

latency_window = deque(maxlen=20)


#risk thresholds mapped from CVSS scores
RISK_THRESHOLDS = {
    "LOW": (0.0, 0.39),
    "MEDIUM": (0.4, 0.69),
    "HIGH": (0.7, 0.89),
    "CRITICAL": (0.9, 1.0)
}

WARNING_FILE = "system_warnings.json"

warning_states = {
    "availability_at_risk_warning":0,
    "availability_under_threshold_warning": 0,
    "high_latency_warning": 0,
    "unmeasured_latency_warning": 0,
    "ttr_high_warning": 0
    
}

def update_warning_state(name, value):
    #updates and saves the warning state to file if changed
    global warning_states
    if warning_states.get(name) != value:
        warning_states[name] = value
        #write to file
        try:
            with open(WARNING_FILE, "w") as f:
                json.dump(warning_states, f, indent=2)
            print(f"[STATE UPDATED] {name} = {value} → file updated.")
        except Exception as e:
            print(f"Error writing warning file: {e}")


r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# ID to read new messages
#the stream associate an ID to each message 
#0 to read all from the beginning, '$' for only new messages
last_id = '0'

#keep track of last availability status to avoid repeated warnings
last_availability_ok = True

#heartbit tracking
last_heartbeat = {}
replica_status = {}
active_count = 0
lock = threading.Lock()

#--------------------------------------------------------------------------------
#                            USEFUL FUNCTIONS
#--------------------------------------------------------------------------------

#to display warning messages
def show_warning(message, color ="red"):
    window = tk.Tk()
    window.title("WARNING")
    window.geometry("400x100")  # dimensione finestra

    label = tk.Label(window, text=message, fg=color)
    label.pack(expand=True)

    window.mainloop()

def evaluate_risk(risk_value):
    #determine the risk level based on the risk value
    for level, (min_val, max_val) in RISK_THRESHOLDS.items():
        if min_val <= risk_value <= max_val:
            return level
    return "UNKNOWN"



#-----------------------------------------------------------------------------
#           AVAILABILITY CHECKS - HEARBEATS AND AVAILABILITY THRESHOLD CHECK
#-----------------------------------------------------------------------------

#HEARTBEAT MONITORING FOR AVAILABILITY
def monitor_heartbeats():
    global active_count
    while True:
        now = int(time.time())
        with lock:
            for replica_id, ts in last_heartbeat.items():
                #Inactive replica
                if replica_status.get(replica_id, True) and now - ts > HEARTBEAT_TIMEOUT:
                    replica_status[replica_id] = False
                    active_count -= 1
                    print(f"Replica {replica_id} no more active! Active count: {active_count}")
                    update_warning_state(f"hb_warning_{replica_id}", 1)

                    if active_count == REPLICA_THRESHOLD:
                        print(" WARNING, YOUR AVAILABILITY IS AT RISK!!!!")
                        update_warning_state("availability_at_risk_warning", 1)
                        #show_warning("WARNING,  if you lose another replica you will not be able to serve requests!!", color= "orange")
                    else:
                        update_warning_state("availability_at_risk_warning", 0)

                    if active_count == QUORUM: #BECAUSE 1 IS BYZANTINE, OTHERWISE < QUORUM IS THE CONDITION
                       print("WARNING, THE SERVICE IS DOWN, YOU CANNOT SERVE REQUESTS WITH THIS NUMBER OF REPLICAS!")
                       update_warning_state("availability_under_threshold_warning", 1)
                       #show_warning("WARNING, THE SERVICE IS DOWN, YOU CANNOT SERVE REQUESTS WITH THIS NUMBER OF REPLICAS!", color= "red")
                    else:
                        update_warning_state("availability_under_threshold_warning", 0)
                    

                # reactivated replica
                elif not replica_status.get(replica_id, True) and now - ts <= HEARTBEAT_TIMEOUT:
                    replica_status[replica_id] = True
                    active_count += 1
                    print(f"Replica {replica_id} reactivated-Active count: {active_count}")
                    update_warning_state(f"hb_warning_{replica_id}", 0)
        time.sleep(1)

def heartbeat_listener():
    pubsub = r.pubsub()
    pubsub.psubscribe(HEARTBEAT_CHANNEL_PATTERN)
    print(f"listen heartbeat on pattern '{HEARTBEAT_CHANNEL_PATTERN}'...")
    for message in pubsub.listen():
        if message['type'] == 'pmessage':
            try:
                data = json.loads(message['data'])
                replica_id = data['replicaId']
                ts = int(data['timestamp']) 
                with lock:
                    last_heartbeat[replica_id] = ts
                    #new replica detected
                    if replica_id not in replica_status:
                        replica_status[replica_id] = True
                        global active_count
                        active_count += 1
                        print(f"new active replica:{replica_id}. Active count: {active_count}")
                        update_warning_state(f"hb_warning_{replica_id}", 0)
            except Exception as e:
                print(f"Error parsing heartbeat: {e}")

# Start heartbeat monitoring thread
threading.Thread(target=monitor_heartbeats, daemon=True).start()
# Start heartbeat listener in a separate thread
threading.Thread(target=heartbeat_listener, daemon=True).start()


#STREAM READING (READ ALL THE INFORMATION FROM THE MONITOR)
#AND AVAILABILITY THRESHOLD CHECK
print(f"Listening to Redis stream '{STREAM_KEY}'... Press Ctrl+C to exit.\n")

try:
    while True:
        # xread read messages from the stream
        # block = 60000 means wait up 1 min (the warnings are showed every 1 min)
        messages = r.xread({STREAM_KEY: last_id}, block=60000)

        for stream_name, msgs in messages:
            for msg_id, msg_data in msgs:
                last_id = msg_id  #update the id to read only new messages next time
                data_json = msg_data.get(b"data")
                if data_json:
                    aggregated_data = json.loads(data_json)
                    print("\nNew aggregated data")
                    print(json.dumps(aggregated_data, indent=2))

        last_av_mex= r.xrevrange(AVAILABILITY_STREAM_KEY, max='+', min='-', count=1)
        if last_av_mex:
            msg_id, msg_data = last_av_mex[0]
            data_json = msg_data.get(b"data")
            if data_json:
                avail_data = json.loads(data_json)
                availability_percent = avail_data.get("availability", {}).get("availability_percent", 100.0)
                print(f"Current availability percent: {availability_percent}%")
                
                if availability_percent < AVAILABILITY_THRESHOLD and last_availability_ok:
                    print(f"CRITICAL WARNING: Availability below threshold ({AVAILABILITY_THRESHOLD}%)! Current: {availability_percent}%")
                    #show_warning("ATTENTION, YOUR AVAILABILITY IS UNDER THE THRESHOLD!", color = "red")
                    last_availability_ok = False
                    update_warning_state("availability_under_threshold_warning", 1)
                elif availability_percent >= AVAILABILITY_THRESHOLD and not last_availability_ok:
                    print(f"INFO: Availability is OK. Current: {availability_percent}%")
                    last_availability_ok = True
                    update_warning_state("availability_under_threshold_warning", 0)
        
#--------------------------------------------------------------------------------
#                                 AVAILABILITY CHECKS - TTR DETECTION
#--------------------------------------------------------------------------------                

        #Analysis of TTR
        ttr_data = aggregated_data.get("ttr", [])
        for entry in ttr_data:
            try:
                ttr_value = float(entry.get("ttr", 0))
                if ttr_value > 86400:  # 1 day in seconds
                    print(f"WARNING:the system has a HIGH TTR ({ttr_value} seconds)")
                    #show_warning(f"The system has a HIGH TTR ({ttr_value} seconds), this can compromise availability!", color="red")
            except ValueError:
                print(f"Warning: not valid TTR value: {entry}")

        
#--------------------------------------------------------------------------------
#                             PERFORMANCE CHECK - LATENCY OF LAST 20 REQUESTS
#--------------------------------------------------------------------------------  
        availability_times = aggregated_data.get("availability_times", [])
        if not availability_times:
            print("WARNING: No latency data available — requests may not be satisfied (system overload?)")
            update_warning_state("unmeasured_latency_warning", 1)
            #show_warning("No latency data — requests not being satisfied (possible overload)", color="orange")
        else:
            update_warning_state("unmeasured_latency_warning", 0)

            for entry in availability_times:
                try:
                    latency_value = float(entry.get("availability_time", 0))
                    latency_window.append(latency_value)
                    print(f"Current latency window: {list(latency_window)}")

                    if len(latency_window) == latency_window.maxlen:
                        avg_latency = sum(latency_window) / len(latency_window)
                        print(f"Average latency (last {latency_window}): {avg_latency:.3f}s")

                        if avg_latency > LATENCY_THRESHOLD:
                            print(f"WARNING: High average latency ({avg_latency:.3f}s) > {LATENCY_THRESHOLD}s")
                            update_warning_state("high_latency_warning", 1)
                            #show_warning(f"High average latency ({avg_latency:.3f}s). Performance at risk!", color="red")

                        else: 
                            update_warning_state("high_latency_warning", 0)
                            print("Latency ok")
                except ValueError:
                    print(f"Warning: not valid latency value: {entry}")

#--------------------------------------------------------------------------------
#                                 AVAILABILITY CHECKS - RISK DETECTION
#--------------------------------------------------------------------------------

        #DEVICES RISK CHECK
        device_risks = aggregated_data.get("device_risks", [])
        for device in device_risks:
            try:
                device_name = device.get("Device", "Unknown")
    

                risk_high_key = f"risk_high_warning_{device_name}"
                risk_critical_key = f"risk_critical_warning_{device_name}"
                ttc_key = f"ttc_risky_warning_{device_name}"

                risk_value = float(device.get("Avg Risk", 0))
                risk_level = evaluate_risk(risk_value)

                #if risk_level == "MEDIUM":
                #    device_name = device.get("Device", "Unknown")
                #    print(f"WARNING: Device '{device_name}' has MEDIUM risk ({risk_value}). Take care")
                #    show_warning(f"Device '{device_name}' has MEDIUM risk ({risk_value}). Pay attention", color="Red")

                if risk_level == "HIGH":
                    
                    print(f"⚠️ WARNING: Device '{device_name}' has HIGH risk ({risk_value})")
                    update_warning_state(risk_high_key, 1)
                    #show_warning(f"Device '{device_name}' has HIGH risk ({risk_value})", color="Red")
                else:
                    update_warning_state(risk_high_key, 0)
                
                if risk_level == "CRITICAL":
                   
                    print(f"WARNING: Device '{device_name}' has CRITICAL risk ({risk_value})")
                    update_warning_state(risk_critical_key, 1)
                    #show_warning(f"Device '{device_name}' has CRITICAL risk ({risk_value})", color="Red")
                else:
                    update_warning_state(risk_critical_key, 0)
                

                #------ ANALYZING THE TTC ------
                ttc_value = float(device.get("TTC", 999))
                if ttc_value < TTC_threshold: 
                    
                    print(f"WARNING: Device '{device_name}' has a risky TTC ({ttc_value})")
                    update_warning_state(ttc_key, 1)
                    #show_warning(f"Device '{device_name}' has a risky TTC ({ttc_value})", color="Red")
                else:
                    update_warning_state(ttc_key, 0)

            except ValueError:
                print(f"Warning: not valid risk value: {device}")



                    

except KeyboardInterrupt:
    print("\nWarning Manager stopped.")