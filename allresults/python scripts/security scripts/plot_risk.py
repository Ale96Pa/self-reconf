import matplotlib.pyplot as plt

#time in seconds of the variuos measurements
time = [0, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000]

#average risk values computed doing the mean of all the deviced for n = 7 - FlexPBFT/10 – 1 failure every 1000 s
average_risk = [
    0.5886, 0.5475, 0.4935, 0.4821, 0.41151, 0.4008,
    0.390, 0.4, 0.42, 0.38, 0.41, 0.42
]

plt.figure(figsize=(8, 5))
plt.plot(time, average_risk, marker='o')

plt.xlabel("Time (s)")
plt.ylabel("Average Risk")
plt.title("Risk trend for n = 7 - FlexPBFT/10 – 1 failure every 1000 s")

plt.grid(True, linestyle="--", alpha=0.6)
plt.tight_layout()
plt.show()
