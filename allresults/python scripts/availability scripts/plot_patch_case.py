import matplotlib.pyplot as plt

#data
scenarios = [
    "FlexPBFT/10\n(no patch)",
    "FlexPBFT/10\n(replaced machines patched)"
]

safe_time_seconds = [
    11000,  #3h 02m 20s
    13000   #3h 36m 40s
]

# Plot
plt.figure(figsize=(8, 5))
plt.bar(scenarios, safe_time_seconds)

#Labels and title
plt.ylabel("Safe Time (seconds)")
plt.title(
    "Safe Time Comparison\n"
    "n = 7, time between requests = 1000 ms"
)

#annotate bars with duration in hours/minutes
labels = ["3h 02m 20s", "3h 36m 40s"]
for i, value in enumerate(safe_time_seconds):
    plt.text(i, value + 200, labels[i], ha='center')

plt.tight_layout()
plt.show()
