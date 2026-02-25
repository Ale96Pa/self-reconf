"""
Keyboard shortcuts during execution:
  - 's'  → Stop the current curve and store it.
  - 'n'  → Start a new curve (automatically stops the current one).
  - 'm'  → Save the current figure in vector format:
              availability_plot.svg
              availability_plot.pdf

SVG and PDF files are fully editable:
  - open them in Inkscape, Adobe Illustrator, or Affinity Designer
  - you can modify colors, line thickness, fonts, labels, legends, and positions
  - each curve appears as a separate graphical object → full visual editing           
"""

import json
import time
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import itertools

JSON_FILE = "availability_results_counters.json"
REFRESH_RATE = 500  

all_curves = []  
current_times = []
current_satisfied = []
is_running = True  # TRUE = curve is being recorded

start_time = time.time()

color_cycle = itertools.cycle(plt.rcParams['axes.prop_cycle'].by_key()['color'])
current_color = next(color_cycle)

def save_editable_plot():
    print("---- SAVING EDITABLE VECTORS ----")
    plt.savefig("availability_plot.svg", format="svg")
    plt.savefig("availability_plot.pdf", format="pdf")
    print("Saved availability_plot.svg and availability_plot.pdf")


def read_json():
    try:
        with open(JSON_FILE, "r") as f:
            data = json.load(f)
            return data.get("satisfied_requests", 0)
    except:
        return None

def stop_curve():
    """Stop and save the current curve."""
    global current_times, current_satisfied, is_running

    if current_times:
        print("---- CURVE STOPPED ----")
        all_curves.append({
            "times": current_times,
            "satisfied": current_satisfied,
            "color": current_color
        })

    is_running = False

def start_new_curve():
    """Start a new curve after stop."""
    global current_times, current_satisfied, start_time, is_running, current_color

    print("---- NEW CURVE START ----")

    current_times = []
    current_satisfied = []
    start_time = time.time()
    current_color = next(color_cycle)
    is_running = True

def on_key(event):
    if event.key == 's':
        stop_curve()
    elif event.key == 'n':
        #If curve is still running, stop it before starting new
        if is_running:
            stop_curve()
        start_new_curve()
    elif event.key == 'm':
        save_editable_plot()

def update(frame):
    if not is_running:
        #Curve stopped -> only redraw existing curves
        plt.cla()

        for i, curve in enumerate(all_curves, start=1):
            plt.plot(
                curve["times"], curve["satisfied"],
                label=f"Run {i}",
                color=curve["color"], linewidth=2, alpha=0.8
            )

        plt.xlabel("Time (seconds)")
        plt.ylabel("Satisfied Requests")
        plt.title("Availability Trend in different scenarios")
        plt.grid(True)
        plt.legend(loc="upper left")
        return

    sr = read_json()
    if sr is None:
        return

    elapsed = time.time() - start_time
    current_times.append(elapsed)
    current_satisfied.append(sr)

    plt.cla()

    #plot all saved curves
    for i, curve in enumerate(all_curves, start=1):
        plt.plot(
            curve["times"], curve["satisfied"],
            label=f"Run {i}",
            color=curve["color"], linewidth=2, alpha=0.8
        )

    #plot live curve
    run_number = len(all_curves) + 1
    plt.plot(
        current_times, current_satisfied,
        label=f"Run {run_number} (Live)",
        color=current_color, linewidth=3
    )

    plt.xlabel("Time (seconds)")
    plt.ylabel("Satisfied Requests")
    plt.title("Availability Trend in different scenarios")
    plt.grid(True)
    plt.legend(loc="upper left")

fig = plt.gcf()
fig.canvas.mpl_connect('key_press_event', on_key)

ani = FuncAnimation(fig, update, interval=REFRESH_RATE)

plt.tight_layout()
plt.show()
