""" Real-time visualization dashboard for PBFT-related metrics"""
import matplotlib.pyplot as plt
import pandas as pd
import json
import os
import matplotlib.ticker as mticker
from pathlib import Path

os.chdir(Path(__file__).resolve().parent)

BASE_DIR = Path(__file__).resolve().parent
METRICS_DIR = BASE_DIR / "metrics"

AVAIL_TIMES_FILE = BASE_DIR / "availability_times.csv"
AVAIL_JSON_FILE = BASE_DIR / "availability_results_counters.json"
RISK_FILE = METRICS_DIR / "device_risks.csv"
TTC_FILE = METRICS_DIR / "ttc.csv"
TTR_FILE = BASE_DIR / "ttr_times.csv"

#Configure plots
plt.ion()  #interactive mode on
fig, axs = plt.subplots(2, 3, figsize=(18, 10))
fig.suptitle("PBFT Real-Time Metrics Dashboard", fontsize=16)

request_numbers = []
availability_history = []



while True:
    try:
        # --- Availability Time ---
        if AVAIL_TIMES_FILE.exists():
            avail_df = pd.read_csv(AVAIL_TIMES_FILE)
            axs.flat[0].cla()
            axs.flat[0].plot(range(1, len(avail_df)+1), avail_df["availability_time"], marker='o', linestyle='-', color='blue')
            axs.flat[0].set_xlabel("Request #")
            axs.flat[0].set_ylabel("Time (s)")
            axs.flat[0].set_title("Availability Time per Request")
            axs.flat[0].grid(True)
        else:
            axs.flat[0].cla()
            axs.flat[0].text(0.5,0.5,"No Availability Times Data", ha='center')
        
        # --- Availability Percentage per Request ---
        if os.path.exists(AVAIL_JSON_FILE):
            with open(AVAIL_JSON_FILE) as f:
                avail_state = json.load(f)
            percent = avail_state.get("availability_percent", 0)
            total_requests = avail_state.get("total_requests", 0)

            if total_requests > 0:
                request_numbers.append(total_requests)
                availability_history.append(percent)

            axs.flat[1].cla()
            axs.flat[1].plot(request_numbers, availability_history, marker='o', linestyle='-', color='green')
            axs.flat[1].set_xlabel("Request #")
            axs.flat[1].set_ylabel("Availability %")
            axs.flat[1].set_ylim(0, 100)
            axs.flat[1].set_title("Availability Percentage per Request")
            axs.flat[1].grid(True)
        
        # --- Average Risk ---
        if os.path.exists(RISK_FILE):
            risk_df = pd.read_csv(RISK_FILE)
            axs.flat[2].cla()
            axs.flat[2].bar(risk_df["Device"], risk_df["Avg Risk"].astype(float), color='orange')
            axs.flat[2].set_title("Average Device Risk")
            axs.flat[2].set_xlabel("Device")
            axs.flat[2].set_ylabel("Risk")
            axs.flat[2].tick_params(axis='x', rotation=45)
            axs.flat[2].grid(axis='y')
        else:
            axs.flat[2].cla()
            axs.flat[2].text(0.5,0.5,"No Risk Data", ha='center')
        
        # --- TTC per Device ---
        if os.path.exists(TTC_FILE):
            ttc_df = pd.read_csv(TTC_FILE)
            axs.flat[3].cla()
            axs.flat[3].bar(ttc_df["Device"], ttc_df["TTC"], color='red')
            axs.flat[3].set_title("Time To Compromise (TTC)")
            axs.flat[3].set_xlabel("Device")
            axs.flat[3].set_ylabel("Days")
            axs.flat[3].tick_params(axis='x', rotation=45)
            axs.flat[3].grid(axis='y')
            axs.flat[3].set_ylim(0, 100)
            axs.flat[3].yaxis.set_major_locator(mticker.MultipleLocator(10))
        else:
            axs.flat[3].cla()
            axs.flat[3].text(0.5,0.5,"No TTC Data", ha='center')
        
        # --- TTR per Request ---
        if os.path.exists(TTR_FILE):
            ttr_df = pd.read_csv(TTR_FILE)
            axs.flat[4].cla()
            axs.flat[4].plot(range(1, len(ttr_df)+1), ttr_df["ttr"], marker='o', linestyle='-', color='purple')
            axs.flat[4].set_xlabel("Failure #")
            axs.flat[4].set_ylabel("TTR (s)")
            axs.flat[4].set_title("Time To Recover (TTR)")
            axs.flat[4].grid(True)
        else:
            axs.flat[4].cla()
            axs.flat[4].text(0.5,0.5,"No TTR Data", ha='center')
        
        

        plt.tight_layout(rect=[0, 0.03, 1, 0.95])
        plt.pause(3)  #update every 3 seconds
    
    except KeyboardInterrupt:
        screenshot_file = BASE_DIR / "PBFT_dashboard.png"
        fig.savefig(screenshot_file)
        print(f"Exiting real-time dashboard... Screenshot saved to {screenshot_file}")
        break