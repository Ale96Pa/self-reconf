#THIS SCRIPT ANALYZES THE BENCHMARK RESULTS AND PRODUCES GRAPHS AND A SUMMARY CSV FILE
import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import re
import numpy as np

BASE_DIR = "results"

summary_avail = []
summary_latency = []

#scanning through all benchmark result directories
for root, dirs, files in os.walk(BASE_DIR):
    match = re.search(r"replicas_(\d+)_requests_(\d+)_interval_(\d+)", root)
    if not match:
        continue
    replicas, requests, interval = map(int, match.groups())

    #availability result counters JSON file
    for file in files:
        if file.startswith("availability_results_counters") and file.endswith(".json"):
            with open(os.path.join(root, file), "r") as f:
                data = json.load(f)
            summary_avail.append({
                "replicas": replicas,
                "requests": requests,
                "interval": interval,
                "availability_percent": data["availability_percent"],
                "total_requests": data["total_requests"],
                "satisfied_requests": data["satisfied_requests"]
            })

    #latency CSV files
    for file in files:
        if file.startswith("availability_times") and file.endswith(".csv"):
            csv_path = os.path.join(root, file)
            df = pd.read_csv(csv_path)
            if "availability_time" not in df.columns:
                continue

            latencies = df["availability_time"].dropna()
            if len(latencies) == 0:
            
                print(f" File vuoto secondo il controllo: {csv_path}")
                print(f"   → Colonne trovate: {df.columns.tolist()}")
                print(f"   → Numero righe totali nel CSV: {len(df)}")
                print(f"   → Valori non nulli in availability_time: {df['availability_time'].count() if 'availability_time' in df.columns else 'colonna mancante'}")
                continue
            else:
                print(f"File valido: {csv_path} ({len(latencies)} valori)")

            summary_latency.append({
                "replicas": replicas,
                "requests": requests,
                "interval": interval,
                "mean_latency": latencies.mean(),
                "median_latency": latencies.median(),
                "std_latency": latencies.std(),
                "p95_latency": np.percentile(latencies, 95)
            })

#create DataFrames
df_avail = pd.DataFrame(summary_avail)
df_lat = pd.DataFrame(summary_latency)

print("\n=== DEBUG DATAFRAMES ===")
print("df_avail shape:", df_avail.shape)
print("df_lat shape:", df_lat.shape)
print("df_avail columns:", df_avail.columns.tolist())
print("df_lat columns:", df_lat.columns.tolist())
print("Prime righe df_avail:")
print(df_avail.head())
print("Prime righe df_lat:")
print(df_lat.head())
print("========================\n")

#join DataFrames on replicas, requests, interval
df_merged = pd.merge(df_avail, df_lat, on=["replicas", "requests", "interval"], how="inner")

# ---------------------------------------------------------
# GRAPH FOR AVAILABILITY: A GRAPH FOR EACH UNIQUE REQUESTS VALUE
# ---------------------------------------------------------

unique_requests = sorted(df_merged["requests"].unique())

for req in unique_requests:
    plt.figure(figsize=(9,6))

    subset = df_merged[df_merged["requests"] == req]

    for replicas, group in subset.groupby("replicas"):
        avg_by_interval = group.groupby("interval")["availability_percent"].mean().sort_index()

        plt.plot(
            avg_by_interval.index,
            avg_by_interval.values,
            marker="o",
            label=f"{replicas} replicas"
        )

    plt.title(f"Availability (%) vs Interval — Requests = {req}")
    plt.xlabel("Time between requests (ms)")
    plt.ylabel("Availability (%)")
    plt.legend(title="Number of replicas")
    plt.grid(True)
    plt.tight_layout()

    plt.savefig(f"availability_vs_interval_replicas_requests_{req}.png")
    plt.show()


#MEAN LATENCY FOR NUM REPLICAS
plt.figure(figsize=(8,5))
lat_by_replicas = df_merged.groupby("replicas")["mean_latency"].mean()
plt.plot(lat_by_replicas.index, lat_by_replicas.values, marker="o", color="orange")
plt.title("Mean latency (%) for number of replicas")
plt.xlabel("Number of replicas")
plt.ylabel("Mean latency (seconds)")
plt.grid(True)
plt.tight_layout()
plt.savefig("latency_vs_replicas.png")
plt.show()

#MEAN LATECY FOR INTERVAL FOR EACH NUMBER OF REPLICAS
plt.figure(figsize=(8,5))
for r in sorted(df_merged["replicas"].unique()):
    subset = df_merged[df_merged["replicas"] == r]
    grouped = subset.groupby("interval")["mean_latency"].mean()
    plt.plot(grouped.index, grouped.values, marker="o", label=f"{r} replicas")

plt.title("Mean latency for each interval (for every number of replicas)")
plt.xlabel("Time between requests (ms)")
plt.ylabel("Mean Latency (seconds)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig("latency_vs_interval.png")
plt.show()

#ANALYSIS OF MAX AND MIN LATENCY AND AVAILABILITY VALUES
#create a table with extreme values for each number of replicas
extreme_records = []

for r in sorted(df_merged["replicas"].unique()):
    subset = df_merged[df_merged["replicas"] == r]

    #Availability MAX
    max_avail_row = subset.loc[subset["availability_percent"].idxmax()]
    extreme_records.append([
        r, "Availability MAX", f"{max_avail_row['availability_percent']:.2f}%", max_avail_row['requests'], max_avail_row['interval']
    ])
    #Availability MIN
    min_avail_row = subset.loc[subset["availability_percent"].idxmin()]
    extreme_records.append([
        r, "Availability MIN", f"{min_avail_row['availability_percent']:.2f}%", min_avail_row['requests'], min_avail_row['interval']
    ])
    # Latency MAX
    max_lat_row = subset.loc[subset["mean_latency"].idxmax()]
    extreme_records.append([
        r, "Latency MAX", f"{max_lat_row['mean_latency']:.3f}s", max_lat_row['requests'], max_lat_row['interval']
    ])
    # Latency MIN
    min_lat_row = subset.loc[subset["mean_latency"].idxmin()]
    extreme_records.append([
        r, "Latency MIN", f"{min_lat_row['mean_latency']:.3f}s", min_lat_row['requests'], min_lat_row['interval']
    ])

#table columns
columns = ["#Replicas", "Metric", "Value", "#Requests", "Interval (ms)"]

#create the table plot
fig, ax = plt.subplots(figsize=(10, len(extreme_records)*0.5 + 1))
ax.axis('off')  #remove axes

#add the table
table = ax.table(cellText=extreme_records, colLabels=columns, cellLoc='center', loc='center')

#formatting
table.auto_set_font_size(False)
table.set_fontsize(10)
table.scale(1, 1.5)  #scale table

plt.title("Extreme value for Availability e Latency based on the number of replicas", fontsize=14, pad=20)
plt.tight_layout()
plt.savefig("extreme_values_table.png", dpi=300)
plt.show()

# ==============================================================================
# 1. HEATMAP Availability (replicas × interval) to visualize bad configurations
# ==============================================================================

pivot_avail = df_merged.pivot_table(
    values="availability_percent",
    index="replicas",
    columns="interval",
    aggfunc="mean"
)

plt.figure(figsize=(10, 6))
plt.imshow(pivot_avail, aspect="auto", cmap="viridis")
plt.colorbar(label="Availability (%)")
plt.xticks(range(len(pivot_avail.columns)), pivot_avail.columns, rotation=45)
plt.yticks(range(len(pivot_avail.index)), pivot_avail.index)
plt.title("Availability Heatmap (Replicas × Interval)")
plt.xlabel("Interval (ms)")
plt.ylabel("Replicas")
plt.tight_layout()
plt.savefig("heatmap_availability.png", dpi=300)
plt.show()


# ==================================================================================================
# 2. HEATMAP Mean Latency (replicas × interval) to visualize configurations that cause high latency
# ==================================================================================================

pivot_latency = df_merged.pivot_table(
    values="mean_latency",
    index="replicas",
    columns="interval",
    aggfunc="mean"
)

plt.figure(figsize=(10, 6))
plt.imshow(pivot_latency, aspect="auto", cmap="inferno")
plt.colorbar(label="Mean Latency (s)")
plt.xticks(range(len(pivot_latency.columns)), pivot_latency.columns, rotation=45)
plt.yticks(range(len(pivot_latency.index)), pivot_latency.index)
plt.title("Mean Latency Heatmap (Replicas × Interval)")
plt.xlabel("Interval (ms)")
plt.ylabel("Replicas")
plt.tight_layout()
plt.savefig("heatmap_latency.png", dpi=300)
plt.show()


# ====================================================================
# 3. Histogram latency to understand distribution of latency
# ====================================================================

plt.figure(figsize=(10, 5))
plt.hist(df_merged["mean_latency"], bins=30)
plt.title("Latency Distribution Histogram")
plt.xlabel("Mean Latency (seconds)")
plt.ylabel("Frequency")
plt.grid(True)
plt.tight_layout()
plt.savefig("histogram_latency.png", dpi=300)
plt.show()


#SAVE RESULTS
df_merged.to_csv("summary_combined.csv", index=False)
print(f"Analysis completed on {len(df_merged)} experiments.")
print("combined results saved on 'summary_combined.csv'.")


