#This is the planner MILP
#the output is a solution printed on console that can be saved in a csv or json file

import csv
import json
import math
from collections import defaultdict
import pulp
import os

DEVICES_FILE = "../analyzer/metrics/device_risks.csv"
CANDIDATES_FILE = "../analyzer/metrics/candidate_risks.csv"
TTC_FILE = "../analyzer/metrics/ttc.csv"
CAND_TTC_FILE = "../analyzer/metrics/candidates_ttc.csv"
MYNETWORK_JSON = "../monitor/ag-basics/MyNetwork.json"
MYCAND_JSON = "../monitor/ag-basics/MyCandidates.json"
WARNING_FILE = "../analyzer/system_warnings.json" 

#weight values for the objective function
alpha = 1.0
beta  = 1.0
delta = 1.0
gamma = 0.01

#for the risk we consider the avg risk across all the attack paths for the single device
RISK_FIELD = "Avg Risk"

# Auto-calc quorum e Rmax
AUTO_CALC_Q = True
AUTO_CALC_RMAX = True

def read_risks_csv(path):
    out = {}
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            device = row.get('Device') or row.get('device') or row.get('Device ')
            if device is None:
                raise ValueError(f"CSV {path} must have 'Device' column")
            #reading avg risk
            R = float(row.get(RISK_FIELD, 0.0))
            #i can use num paths to compute weighted risk if needed
            num_paths = int(float(row.get('Num Paths', 0))) if row.get('Num Paths') not in (None, '') else 0
            out[device.strip()] = {'R': R, 'num_paths': num_paths}
    return out

def read_ttc_csv(path):
    #reading TTC from csv file
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        for row in r:
            device = row.get('Device') or row.get('device')
            if device is None:
                continue
            t = row.get('TTC') or row.get('Ttc') or row.get('ttc')
            try:
                TTC = float(t)
            except:
                TTC = 0.0
            out[device.strip()] = TTC
    return out

def read_features_from_json(path):
    #read the json file of the network and extract the CVE sets for each device
    out = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding='utf-8') as f:
        j = json.load(f)
    devices = j.get('devices', [])
    for dev in devices:
        key = None
        if 'ipaddress' in dev and dev['ipaddress']:
            key = dev['ipaddress'].strip()
        elif 'hostname' in dev and dev['hostname']:
            key = dev['hostname'].strip()
        else:
            # skip device without valid key
            continue
        cves = set()
        for iface in dev.get('network_interfaces', []):
            for port in iface.get('ports', []):
                for svc in port.get('services', []):
                    for c in svc.get('cve_list', []) or []:
                        if c and isinstance(c, str):
                            cves.add(c.strip())
        out[key] = cves
    return out

def read_warnings_json(path):
    #Reading system_warnings.json and return a dict of warnings
    #if the file does not exist or is not valid, return empty dict
    
    if not os.path.exists(path):
        print(f"[WARN] warning file {path} not found. Continuing with empty warnings.")
        return {}
    with open(path, encoding='utf-8') as f:
        try:
            j = json.load(f)
            if not isinstance(j, dict):
                print(f"[WARN] {path} content not a JSON object. Ignoring.")
                return {}
            return j
        except Exception as e:
            print(f"[WARN] error reading {path}: {e}")
            return {}

#compute diversity using Jaccard similarity
def jaccard_diversity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    inter = len(set_a.intersection(set_b))
    union = len(set_a.union(set_b))
    if union == 0:
        return 1.0
    J = inter / union
    return 1.0 - J

device_to_idx = {
    "192.168.56.110": 0,
    "192.168.56.111": 1,
    "192.168.56.112": 2,
    "192.168.56.113": 3,
    "192.168.56.114": 4,
    "192.168.56.115": 5,
    "192.168.56.116": 6,
    "192.168.56.117": 7,
    "192.168.56.118":8
}

def build_and_solve(devices_info, candidates_info, ttc_dev, ttc_cand, feats_dev, feats_cand,
                    warnings_map, alpha, beta, delta, gamma, Q=None, Rmax=None):
    #merge information into structures used dal MILP
    M_list = sorted(list(devices_info.keys()))
    C_list = sorted(list(candidates_info.keys()))
    
    #build devices dict including warnings mapping -> set S, W_rep, W_hb
    devices = {}
    for d in M_list:
        R = devices_info[d]['R']
        T = ttc_dev.get(d, 0.0)
        #derive warning-based flags
        idx = device_to_idx.get(d)
        if idx is not None:
            hb_key = f"hb_warning_{idx}"
            hb_val = int(warnings_map.get(hb_key, 0))
            S = 0 if hb_val == 1 else 1
            W_hb = hb_val
        else:
            S = 1
            W_hb = 0

        risk_high_key = f"risk_high_warning_{d}"
        risk_critical_key = f"risk_critical_warning_{d}"
        ttc_risky_key = f"ttc_risky_warning_{d}"

        risk_high_val = int(warnings_map.get(risk_high_key, 0))
        risk_critical_val = int(warnings_map.get(risk_critical_key, 0))
        ttc_risky_val = int(warnings_map.get(ttc_risky_key, 0))

        # W_rep: we set replacement request if any risk or ttc warning is present
        #if w_hb ==1 we prefer to migrate rather than replace -> no replacement needed
        W_rep = 1 if (risk_high_val == 1 or risk_critical_val == 1 or ttc_risky_val == 1)and (W_hb == 0)  else 0

        t_down = 10.0
        features = feats_dev.get(d, set())
        devices[d] = {
            'R': R, 'T': T, 'S': S, 'W_rep': W_rep, 'W_hb': W_hb,
            't_down': t_down, 'features': features,
            'warnings': {
                'hb': hb_val,
                'risk_high': risk_high_val,
                'risk_critical': risk_critical_val,
                'ttc_risky': ttc_risky_val
            }
        }

    # Build candidates dict (they might also have warnings but usually not)
    candidates = {}
    for c in C_list:
        R = candidates_info[c]['R']
        T = ttc_cand.get(c, 0.0)
        features = feats_cand.get(c, set())
        candidates[c] = {'R': R, 'T': T, 'features': features}

    nM = len(M_list)
    nC = len(C_list)

    #compute Q and Rmax if needed
    if Q is None and AUTO_CALC_Q:
        f = max(0, (nM - 1) // 3)
        Q = 2 * f + 1
        if Q < 1:
            Q = 1
    if Rmax is None and AUTO_CALC_RMAX:
        Rmax = max(0, nM - Q)

    #diversity matrix e D_i (max diversity against candidates)
    diversity = {}
    for i in M_list:
        for j in C_list:
            diversity[(i,j)] = jaccard_diversity(devices[i]['features'], candidates[j]['features'])
    D_i = {}
    for i in M_list:
        if nC == 0:
            D_i[i] = 0.0
        else:
            D_i[i] = max(diversity[(i,j)] for j in C_list)

    # ---------------- MILP ----------------
    prob = pulp.LpProblem("PBFT_Planner_From_Files_With_Warnings", pulp.LpMinimize)

    x = pulp.LpVariable.dicts("x", M_list, cat="Binary")
    y = pulp.LpVariable.dicts("y", C_list, cat="Binary")
    r = pulp.LpVariable.dicts("r", [(i,j) for i in M_list for j in C_list], cat="Binary")
    a = pulp.LpVariable.dicts("a", [(d,j) for d in M_list for j in C_list], cat="Binary")

    #hartbeat/migrate constraint: if W_hb==1 sum a_d_j == 1 and a <= y
    for d in M_list:
        if devices[d]['W_hb'] == 1:
            prob += pulp.lpSum(a[(d,j)] for j in C_list) == 1, f"hb_migrate_exactly_one_{d}"
            for j in C_list:
                prob += a[(d,j)] <= y[j], f"hb_a_link_y_{d}_{j}"

    PENALTY_MISSING_REP = 50.0
    missing_rep = {}
    #replacement constraints W_rep: x_i == 0, sum r_i_j == 1, r <= y
    for i in M_list:
        if devices[i]['W_rep'] == 1:
                
                missing_rep[i] = pulp.LpVariable(f"missing_rep_{i}", lowBound=0, upBound=1, cat="Binary")
                #prob += x[i] == 0, f"replace_forced_x0_{i}"
                #prob += pulp.lpSum(r[(i,j)] for j in C_list) == 1, f"replace_exactly_one_{i}"
                for j in C_list:
                    prob += r[(i,j)] <= y[j], f"replace_link_y_{i}_{j}"
                    prob += r[(i,j)] <= 1 - x[i], f"soft_replace_conflict_x_{i}_{j}"

                #devices[i]['reason'] = f"replaced by candidates"
                prob += pulp.lpSum(r[(i,j)] for j in C_list) + missing_rep[i] == 1, \
                f"soft_replacement_balance_{i}"

                devices[i]['reason'] = f"replacement requested (soft)"
        
        else:
                devices[i]['reason'] = "normal keep"

    
    #if kept, cannot be replaced
    for i in M_list:
        for j in C_list:
            prob += r[(i,j)] <= 1 - x[i], f"replace_conflict_keep_{i}_{j}"

    #quorum
    prob += pulp.lpSum(x[i] for i in M_list) + pulp.lpSum(y[j] for j in C_list) >= Q, "quorum_constraint"

    #max simultaneous replacements
    prob += pulp.lpSum(1 - x[i] for i in M_list) <= Rmax, "max_replacements"

    # If device is S==0 cannot be kept
    for i in M_list:
        if devices[i]['S'] == 0:
            prob += x[i] <= 0, f"cannot_keep_down_{i}"

    for j in C_list:
            # Max one replacement for devices that have W_rep
        prob += pulp.lpSum(r[(i,j)] for i in M_list if devices[i]['W_rep'] == 1) <= 1, \
                f"candidate_max_1_replacement_{j}"

        # Max one migration for devices that have W_hb
        prob += pulp.lpSum(a[(d,j)] for d in M_list if devices[d]['W_hb'] == 1) <= 1, \
                f"candidate_max_1_migration_{j}"

        # Mutual exclusion: one candidate can be used or for replacement or migration
        prob += (
            pulp.lpSum(r[(i,j)] for i in M_list if devices[i]['W_rep'] == 1) +
            pulp.lpSum(a[(d,j)] for d in M_list if devices[d]['W_hb'] == 1) 
        ) <= 1, f"candidate_one_use_only_{j}"

        #activation of candidate only if really used
        prob += y[j] <= (
            pulp.lpSum(r[(i,j)] for i in M_list if devices[i]['W_rep'] == 1) +
            pulp.lpSum(a[(d,j)] for d in M_list if devices[d]['W_hb'] == 1) 
        ), f"candidate_active_only_if_used_{j}"
        


    high_latency_val = int(warnings_map.get("high_latency_warning", 0))
    soft_skip_var = None
    if high_latency_val == 1:

        eligible = [
        i for i in M_list
        if devices[i]['S'] == 1 and devices[i]['W_rep'] == 0 and devices[i]['W_hb'] == 0
        ]
        if len(eligible) == 0:
            # Nothing to enforce; skip
            print("[WARN] High-latency warning but no eligible devices to turn off — skipping constraint.")
        else:
            # force activation of at least one candidate
            # compute lower ttc
            min_ttc = min(devices[i]['T'] for i in eligible)
            min_ttc_devices = [i for i in eligible if devices[i]['T'] == min_ttc]

            # 2) Soft variable: allows skipping the constraint
            soft_skip_var = pulp.LpVariable("soft_high_latency_skip", lowBound=0, upBound=1, cat="Binary")

            # 3) Soft constraint:
            #    Either exactly one of the worst-risk eligible devices is turned off
            #    OR skip=1 (relaxes the constraint)
            prob += (
                pulp.lpSum((1 - x[i]) for i in min_ttc_devices) + soft_skip_var == 1
            ), "soft_high_latency_turnoff"

            # 4) Objective penalty for skipping
            PENALTY = 10_000  # large enough to strongly discourage skipping
            prob += PENALTY * soft_skip_var
    
    
    #objective function terms
    term_alpha = pulp.lpSum(devices[i]['R'] * x[i] for i in M_list)
    term_beta  = pulp.lpSum(devices[i]['T'] * x[i] for i in M_list)
    term_delta = pulp.lpSum(D_i[i] * x[i] for i in M_list)
    term_gamma = pulp.lpSum(devices[i]['t_down'] * (1 - x[i]) for i in M_list)
    term_alpha_cand = pulp.lpSum(candidates[j]['R'] * y[j] for j in C_list)
    term_beta_cand = pulp.lpSum(candidates[j]['T'] * y[j] for j in C_list)



    penalty_missing = pulp.lpSum(missing_rep[i] * PENALTY_MISSING_REP 
                             for i in missing_rep)

    prob += alpha * term_alpha + alpha*term_alpha_cand - beta * term_beta - beta*term_beta_cand - delta * term_delta + gamma * term_gamma + penalty_missing, "Objective"

    #solve
    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]
    print("Solver status:", status)
    if status != "Optimal":
        print("[WARN] Solver did not find optimal solution.")

    #extract solution
    sol = {
        'x': {i: int(pulp.value(x[i]) or 0) for i in M_list},
        'y': {j: int(pulp.value(y[j]) or 0) for j in C_list},
        'r': {(i,j): int(pulp.value(r[(i,j)])or 0) for i in M_list for j in C_list},
        'a': {(d,j): int(pulp.value(a[(d,j)]) or 0) for d in M_list for j in C_list},
        'objective': pulp.value(prob.objective),
        'Q': Q,
        'Rmax': Rmax,
        'D_i': D_i,
        'diversity': diversity,
        'devices': devices  #return devices with warning metadata for inspection
    }

    # --- track which device was turned off due to high-latency ---
    high_latency_shutdown = None
    if soft_skip_var is not None:
        skip_val = int(pulp.value(soft_skip_var) or 0)
        if skip_val == 0:
            # exactly one of the max-risk devices should be off
            turned_off = [i for i in min_ttc_devices if sol['x'][i] == 0]
            if len(turned_off) == 1:
                high_latency_shutdown = turned_off[0]
        # track devices that could have been turned off but non idonei per vincoli
        high_latency_candidates = [
            i for i in min_ttc_devices
            if devices[i]['S'] == 1 and devices[i]['W_rep'] == 0 and devices[i]['W_hb'] == 0
        ]

    sol['high_latency_shutdown'] = high_latency_shutdown
    if soft_skip_var is not None:
        sol['high_latency_candidates'] = high_latency_candidates
    else:
        sol['high_latency_candidates'] = []
    return sol, devices, candidates



if __name__ == "__main__":
    # 1) read risks
    dev_risks = read_risks_csv(DEVICES_FILE)
    cand_risks = read_risks_csv(CANDIDATES_FILE)

    # 2) read ttc and cand_ttc
    ttc_dev = read_ttc_csv(TTC_FILE)
    ttc_cand = read_ttc_csv(CAND_TTC_FILE)

    # 3) read features from json files
    feats_dev = read_features_from_json(MYNETWORK_JSON)
    feats_cand = read_features_from_json(MYCAND_JSON)

    # 4)read warnings
    warnings_map = read_warnings_json(WARNING_FILE)

    print(f"Loaded {len(dev_risks)} devices, {len(cand_risks)} candidates.")
    print(f"Found TTC entries: {len(ttc_dev)} devices, {len(ttc_cand)} candidates.")
    print(f"Found features (CVE) entries: {len(feats_dev)} devices, {len(feats_cand)} candidates.")
    print(f"Found warnings entries: {len(warnings_map)} keys.")

    sol, devices, candidates = build_and_solve(dev_risks, cand_risks, ttc_dev, ttc_cand, feats_dev, feats_cand,
                                              warnings_map, alpha, beta, delta, gamma)

    print("\n--- SOLUTION ---")
    print(f"Objective: {sol['objective']}")
    print("Kept devices (x=1):")
    for i, v in sol['x'].items():
        if v == 1:
            reason = sol['devices'][i].get('reason', '')
            print("  ", i, f"({reason})")
    print("Activated candidates (y=1):")
    for j, v in sol['y'].items():
        if v == 1:
            print("  ", j)
    print("Replacements r_i_j:")
    for (i,j), val in sol['r'].items():
        if val == 1:
            print("  ", j, "replaces", i)
    print("Migrations a_d_j:")
    for (d,j), val in sol['a'].items():
        if val == 1:
            print("  ", d, "->", j)
    
    high_latency_val = int(warnings_map.get("high_latency_warning", 0))
    if sol['high_latency_shutdown']:
        print("\nA risky device sholud be turned off due to high-latency of the system:", sol['high_latency_shutdown'])
    elif sol.get('high_latency_candidates'):
        print("\nHigh-latency warning active, but no devices can be turned off due to constraints.")
        print("Candidate devices that can not be turned off but was candidates:", ", ".join(sol['high_latency_candidates']))

    print("\n--- DEVICES & WARNINGS (input translation) ---")
    for d, meta in sol['devices'].items():
        w = meta.get('warnings', {})
        print(f"{d}: S={meta['S']} W_hb={meta['W_hb']} W_rep={meta['W_rep']} warnings={w}")

    print("\n--- GLOBAL SYSTEM WARNINGS ---")
    for key, val in warnings_map.items():
        if not any(dev in key for dev in sol['devices'].keys()):
            print(f"{key}: {val}")

   
