"""
This script models and simulates PBFT system performance based on real latency and availability data. The script depends on 
PBFT because it analyzes metrics (latency and availability) that are influenced by the PBFT protocol's behavior.

Steps:
1. Load real measurements of latency (from CSV) and availability (from JSON).
2. Compute descriptive statistics (mean, standard deviation, 95th percentile, availability).
3. Fit a lognormal distribution to the real latency data.
4. Run a Monte Carlo simulation to generate synthetic latency samples.
5. Introduce a correlation between latency and availability (higher latency → lower availability) and a little noise
6. Compute simulated statistics and compare them to real data.
7. Visualize both real and simulated latency distributions using kernel density estimation (KDE).

Purpose:
To create a realistic statistical model of PBFT performance that can be used for predicti
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
import json
from scipy.stats import lognorm, gaussian_kde

# ==========================
#Load real data
# ==========================
script_dir = os.path.dirname(os.path.abspath(__file__))

latency_file = os.path.join(script_dir, "availability_times.csv")
availability_file = os.path.join(script_dir, "availability_results_counters.json")

#Read real latencies
data = pd.read_csv(latency_file)
real_latencies = data["availability_time"].values

#read real availability
with open(availability_file, "r") as f:
    availability_data = json.load(f)
total_requests = availability_data["total_requests"]
satisfied_requests = availability_data["satisfied_requests"]
real_availability = satisfied_requests / total_requests

# ==========================
#real statistics
# ==========================
# Compute descriptive statistics of the real data:
# - mean: typical latency
# - std: variability of latency
# - 95th percentile: value below which 95% of latencies fall, important
#   to understand worst-case but not extreme outliers
# - real availability: ratio of satisfied requests to total requests
mean_real = np.mean(real_latencies)
std_real = np.std(real_latencies)
p95_real = np.percentile(real_latencies, 95)

print("=== Real Statistics ===")
print(f"Mean Latency: {mean_real:.4f} s")
print(f"Standard deviation: {std_real:.4f} s")
print(f"95° percentile: {p95_real:.4f} s")
print(f"Real availability: {real_availability*100:.2f}%")

# ==========================
# 3.Fit lognormal distribution
# ==========================
# We use a lognormal distribution because latencies are always positive
# and most requests are fast, while a few take much longer.
# The lognormal fits well because it can model this pattern,
# showing both normal and rare slow events.

shape, loc, scale = lognorm.fit(real_latencies, floc=0)

# ==========================
# 4.Monte Carlo Simulation
# ==========================
# Generate a large number of synthetic latency samples based on the fitted lognormal.
# Monte Carlo sampling allows exploring likely latency values beyond the exact
# observed data, providing a probabilistic prediction of system performance.
num_sim = 2000  #number of simulations

#simulate realistic latencies with lognormal distribution
simulated_latencies = lognorm.rvs(shape, loc=loc, scale=scale, size=num_sim)


#Adds small random noise to simulate natural variability
simulated_availability = []
for l in simulated_latencies:
    noise = np.random.normal(0, 0.005)
   # penalty = 0.03 * (l / p95_real) if l > p95_real else 0 e
    value = np.clip(real_availability + noise, 0, 1)
    simulated_availability.append(value)
simulated_availability = np.array(simulated_availability)

# ==========================
#Simulated statistics
# ==========================
mean_sim = np.mean(simulated_latencies)
std_sim = np.std(simulated_latencies)
p95_sim = np.percentile(simulated_latencies, 95)
mean_availability = np.mean(simulated_availability)

print("\n=== Simulated statistics ===")
print(f"Expected mean latency: {mean_sim:.4f} s")
print(f"Expected standard deviation: {std_sim:.4f} s")
print(f"Expected 95° percentile: {p95_sim:.4f} s")
print(f"Expected Availability: {mean_availability*100:.2f}%")

# ==========================
#visualization
# ==========================
# Visual comparison of real vs simulated latency distributions:
# - Kernel Density Estimation (KDE) is used to visualize the shape of distributions.
# - Mean lines help to compare central tendencies.

plt.figure(figsize=(10,6))

# real KDE
kde_real = gaussian_kde(real_latencies)
x_real = np.linspace(min(real_latencies), max(real_latencies), 300)
plt.plot(x_real, kde_real(x_real), color="blue", linewidth=2, label="Real")

#simulated KDE
kde_sim = gaussian_kde(simulated_latencies)
x_sim = np.linspace(min(simulated_latencies), max(simulated_latencies), 300)
plt.plot(x_sim, kde_sim(x_sim), color="orange", linewidth=2, label="Simulated (Lognorm)")

#mean lines
plt.axvline(mean_real, color="blue", linestyle="--", linewidth=1.5, label=f"Real Mean: {mean_real:.3f}s")
plt.axvline(mean_sim, color="orange", linestyle="--", linewidth=1.5, label=f"Simulated mean: {mean_sim:.3f}s")

plt.xlabel("Latency (s)")
plt.ylabel("Density")
plt.title("Confronto PBFT: Real latency vs Simulated Latency (lognormal model)")
plt.legend()
plt.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
plt.savefig("latency_distributions.png", dpi=300)
print("Graph saved as 'latency_distributions.png'")
plt.show()

# ==========================
# Save results
# ==========================

#Save simulated statistics summary
summary = pd.DataFrame({
    "mean_latency_simulated": [mean_sim],
    "mean_availability_simulated": [mean_availability]
})

summary.to_csv("simulated_expectation_performance_model.csv", index=False)

print("Simulated statistics saved in 'simulated_statistics_summary.csv'")
results = pd.DataFrame({
    "simulated_latency": simulated_latencies,
    "simulated_availability": simulated_availability
})
results.to_csv("performance_model_data.csv", index=False)

print("\nresults saved in 'performance_model_data.csv'")
