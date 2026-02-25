import matplotlib.pyplot as plt

#time
time = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000]

#mean ttc values between all devices at each iteration of the planner
ttc = [
    27.95, 32.14, 32.58, 32.63, 32.71, 32.328,
    32.33, 32.1, 32.0, 32.84, 32.154, 33.99
]

plt.figure(figsize=(8, 5))
plt.plot(time, ttc, marker='o')

plt.xlabel("Time (s)")
plt.ylabel("average TTC")
plt.title("TTC trend for n = 7 – FlexPBFT/10 – 1 failure every 1000 s")

plt.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()
