import matplotlib.pyplot as plt
import numpy as np


labels = [
    "Static PBFT",
    "FlexPBFT/1",
    "FlexPBFT/5",
    "FlexPBFT/10",
    "FlexPBFT/20"
]


safe_time_4 = [2000, 3000, 7000, 12000, 22000]
safe_time_7 = [3000, 4000, 6000, 11000, 21000]
safe_time_19 = [7000, 8000, 8000, 9000, 18000]


x = np.arange(3)  
bar_width = 0.15


plt.figure(figsize=(10, 6))


for i in range(len(labels)):
    plt.bar(
        x + i * bar_width,
        [safe_time_4[i], safe_time_7[i], safe_time_19[i]],
        width=bar_width,
        label=labels[i]
    )


plt.ylabel("Safe time (s)")
plt.xlabel("Number of replicas")


plt.xticks(
    x + bar_width * 2,
    ["4 replicas", "7 replicas", "19 replicas"]
)


plt.grid(axis="y", linestyle="--", alpha=0.6)
plt.legend()


plt.tight_layout()
plt.show()
