"""
This script depends on PBFT because it simulates a PBFT system using a Continuous-Time Markov Chain (CTMC)
and Monte Carlo methods to estimate system-level metrics such as availability, MTTF, and MTTR.
"""
import numpy as np
import itertools
import matplotlib.pyplot as plt
import pandas as pd
import json

#The simulation models a PBFT system as a Continuous-Time Markov Chain (CTMC):
#1. Each replica changes state (UP/DOWN) at random times, exponentially distributed.
#2. The next state depends only on the current one (Markov property).
#3. Each transition has an associated rate: lambda (failure) and mu (repair).
#4. The system is UP if at least quorum (= 2f+1) replicas are operational.
#A Monte Carlo approach is used to repeat the stochastic simulation multiple times
#and estimate system-level metrics such as availability, MTTF, and MTTR.

#i use CTMC as a model to describe the dynamic behavior of the system over time
#i use Monte Carlo to repeat the simulation multiple times to get statistical estimates

#params of my pbft system
n = 7               #number of replicas
f = 2                #max tolerable byzantines
quorum = 2*f + 1    #quorum size for pbft #(add +1 if we consider that 1 replica is sending incorrect answers)
simulation_time = 10000  #hours of simulation
num_runs = 100 #number of monte carlo runs


#lambda and mu for each replica (can be different based on OS and services that run on them)
lambda_replicas = [0.00012, 0.00012, 0.00012, 0.00011, 0.00011, 0.00015, 0.00015]  #failure rates (guasti/ora) 1/0,00012 = 8333 hours 
mu_replicas     = [0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]                #repair rates (ripristini/ora) 1/0,1 = 10 hours

#Initializing replicas' states (True = UP, False = DOWN)
def simulate_once(lambda_replicas, mu_replicas, f):
    n = len(lambda_replicas)
    quorum = 2*f + 1
    replicas = [True] * n  #True = UP, False = DOWN
    t = 0
    timeline = [(0, True)] #(time, system_state)

    crash_count = [0] * n
    max_down = 0

    def system_state(replicas, quorum):
        #return True if the quorum is reached (UP), False otherwise (DOWN)
        return sum(replicas) >= quorum

    #simulation loop
    #for each replica, decide when the next event (failure or repair) will happen
    #if the replica is UP, the event is a failure (interval = exp (lambda)) 
    #if the replica is DOWN, the event is a repair (interval = exp (mu))
    while t < simulation_time:
        times_to_event = []
        for i, up in enumerate(replicas):
            rate = lambda_replicas[i] if up else mu_replicas[i]
            #generating a random time until the next event following an exponential distribution 
            dt = np.random.exponential(1 / rate)
            times_to_event.append(dt)
        
        #find the next event more near in the future between all replicas
        min_dt = min(times_to_event)
        #update simulation time
        t += min_dt
        
        #update the state of the replica that has the next event
        event_index = times_to_event.index(min_dt)

         #Crash check
        if replicas[event_index] == True:  #go down
            crash_count[event_index] += 1

        replicas[event_index] = not replicas[event_index]  #switch UP-DOWN

        #number of DOWN replicas
        num_down = replicas.count(False)
        if num_down > max_down:
            max_down = num_down
        
        #update the timeline with the new state of the system
        #Even if the system stays UP (quorum satisfied), a new event is recorded in the timeline 
        #whenever a replica changes state, potentially closing and reopening an identical UP period.
        #this is the reason why the MTTF is different from the entire simulation time even if availability is 100%
        timeline.append((t, system_state(replicas, quorum)))

    #analysis of the timeline to extract UP/DOWN periods and compute metrics
    up_periods = []
    down_periods = []
    #initializing previous time and state
    prev_time = 0
    prev_state = timeline[0][1]

    #iterating over the timeline to compute UP and DOWN periods
    for curr_time, curr_state in timeline[1:]:
        dt = curr_time - prev_time
        if prev_state:
            up_periods.append(dt)
        else:
            down_periods.append(dt)
        prev_time = curr_time
        prev_state = curr_state

    #considering the last period until the end of the simulation
    dt = simulation_time - prev_time
    if prev_state:
        up_periods.append(dt)
    else:
        down_periods.append(dt)

    #computing metrics from the simulation
    MTTF = np.mean(up_periods) #Mean Time To Failure of the system (average uptime duration between system-level failures)
    MTTR = np.mean(down_periods)
    availability = sum(up_periods) / simulation_time

    return availability, MTTF, MTTR, timeline, crash_count, max_down

# ===================================
#  MONTE CARLO MULTUPLE RUNS
# ===================================
#although lamda and mu are always the same, the random exponential generation of events leads to different results at each run
results = [simulate_once(lambda_replicas, mu_replicas, f) for _ in range(num_runs)]
availabilities, mttfs, mttrs, timelines, crash_counts, max_downs  = zip(*results)

print("=== MONTE CARLO RESULTS (mean based on more runs) ===")
print(f"Mean Availability: {np.mean(availabilities)*100:.5f}% ± {np.std(availabilities)*100:.5f}")
print(f"Mean MTTF: {np.mean(mttfs):.2f} h ± {np.std(mttfs):.2f}") 
print(f"Mean MTTR: {np.mean(mttrs):.2f} h ± {np.std(mttrs):.2f}")
print(f"Mean max DOWN replicas at the same time: {np.mean(max_downs):.2f}")
print(f"Mean number of crash per replica: {np.mean(crash_counts, axis=0)}")

#save results summary to json
summary = {
    "mean_availability": float(np.mean(availabilities)),
    "mean_MTTF": float(np.mean(mttfs)),
    "mean_MTTR": float(np.mean(mttrs)),
    "mean_max_down": float(np.mean(max_downs)),
    "crash_count_mean_per_replica": list(np.mean(crash_counts, axis=0))
}

with open("pbft_montecarlo_simulation_results.json", "w") as f:
    json.dump(summary, f, indent=4)



# ======================================
# PLOTTING THE TIMELINE OF A SINGLE RUN
# ======================================
timeline = results[0][3]
times = [0] + [t for t,_ in timeline]
states = [timeline[0][1]] + [s for _,s in timeline]
states_num = [1 if s else 0 for s in states]

plt.step(times, states_num, where='post')
plt.ylim(-0.1, 1.1)
plt.xlabel('Time (hours)')
plt.ylabel('State of the system (1=UP, 0=DOWN)')
plt.title('Evolution of a  PBFT state (1 simulation)')
plt.show()

#================================
#sensitivity analysis
#================================

#Varying lambda and mu, n and f to see their impact on availability

availability_threshold = 0.999
n_values = [4, 7, 10, 16, 22, 31]
f_values_dict = {4:[1], 7:[2], 10:[3], 16:[5], 22:[7], 31:[10]}

lambda_values = [0.0001, 0.001, 0.01] 
mu_values = [0.1, 0.3, 0.5]

num_runs_param_scan = 20

def generate_lambda_mu_list(n, lam_val, mu_val):
    return [lam_val]*n, [mu_val]*n

critical_combinations = []

for n_scan in n_values:
    for f_scan in f_values_dict[n_scan]:
        quorum_scan = 2*f_scan + 1
        for lam_val, mu_val in itertools.product(lambda_values, mu_values):
            lambda_rep, mu_rep = generate_lambda_mu_list(n_scan, lam_val, mu_val)

            #monte carlo simlation for this param combination
            results_scan = [simulate_once(lambda_rep,mu_rep,f_scan ) for _ in range(num_runs_param_scan)]
            availabilities_scan = [res[0] for res in results_scan]
            mean_av = np.mean(availabilities_scan)

            if mean_av < availability_threshold:
                critical_combinations.append({
                    'n': n_scan,
                    'f': f_scan,
                    'lambda': lam_val,
                    'mu': mu_val,
                    'availability': mean_av
                })

#print crtitical combinations
print("\n=== Critical combinations (availability < 99.9%) ===")
for comb in critical_combinations:
    print(comb)

#create a DataFrame pandas to visualize better the critical combinations
df_critical = pd.DataFrame(critical_combinations)

df_critical = df_critical.sort_values(['n','f','lambda','mu'])

#draw table
fig, ax = plt.subplots(figsize=(10, len(df_critical)*0.5 + 1))
ax.axis('tight')
ax.axis('off')
table = ax.table(cellText=df_critical.values,
                 colLabels=df_critical.columns,
                 cellLoc='center',
                 loc='center')
table.auto_set_font_size(False)
table.set_fontsize(10)
table.auto_set_column_width(col=list(range(len(df_critical.columns))))

plt.title("Critical combinations(availability < 99.9%)", fontsize=14)
plt.tight_layout()
plt.savefig("critical_situations_MC-CTMC.png", dpi=300)
plt.show()

