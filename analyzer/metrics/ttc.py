"""The TTC formula is based on the paper: Estimating a system Mean time to compromise (MTTC)"""
import json
import csv
import math
from pathlib import Path
import requests

compute_for_candidates = True

script_dir = Path(__file__).resolve().parent

if compute_for_candidates:
    NETWORK_FILE = script_dir.parents[1] / "monitor" / "ag-basics" / "MyCandidates.json"
    TTC_CSV_FILE = script_dir /"candidates_ttc.csv"

else:
    NETWORK_FILE = script_dir.parents[1] / "monitor" / "ag-basics" / "MyNetwork.json"
    TTC_CSV_FILE = script_dir /"ttc.csv"


CISA_KEV_JSON = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

# EPSS API base
EPSS_API = "https://api.first.org/data/v1/epss"

s = 0.9 #a little bit less than intermediate attacker
t1 = 1 #day

#load KEV list - returns a set of CVE strings in uppercase
def load_kev_set():
    r = requests.get(CISA_KEV_JSON, timeout=30)
    r.raise_for_status()
    data = r.json()
    kev_cves = set()
    #parsing
    for item in data.get("vulnerabilities", []) if "vulnerabilities" in data else data.get("rows", []):
        #try various possible keys
        if isinstance(item, dict):
            cve = item.get("cveID") or item.get("cve") or item.get("cve_id") or item.get("CVE")
            if cve:
                kev_cves.add(cve.strip().upper())
        else:
            #if it is a string
            kev_cves.add(str(item).strip().upper())
    return kev_cves

#query EPSS for a list of CVEs, returns a map cve -> epss score (float) 
#that represents the probability that a vulnerability will be exploited
def batch_epss_query(cve_list):
    #i divide in batches of 200 CVEs to avoid too long URLs
    batch_size = 200
    #dictionary cve -> epss score
    epss_map = {}
    #iterate over batches and perform requests to EPSS API
    for i in range(0, len(cve_list), batch_size):
        batch = cve_list[i:i+batch_size]
        q = ",".join(batch)
        params = {"cve": q}
        r = requests.get(EPSS_API, params=params, timeout=30)
        r.raise_for_status()
        js = r.json()
        #the api can  return json with key "data" or "results" othewise it assumes that the answer is the json itself
        results = js.get("data") or js.get("results") or js
        #if result is a list of obj for each one it takes the key "cve" and the probability "epss" 
        if isinstance(results, list):
            for item in results:
                cve = item.get("cve")
                epss = item.get("epss") or item.get("probability") or item.get("score")
                try:
                    #convert it in float
                    epss_map[cve.upper()] = float(epss)
                except:
                    epss_map[cve.upper()] = 0.0
        elif isinstance(results, dict):
            for item in results:
                pass
    return epss_map

kev_set = load_kev_set()

#obtain total number of CVEs from NVD feed
def get_total_nvd_cve():
    url = "https://services.nvd.nist.gov/rest/json/cves/2.0?startIndex=0&resultsPerPage=1"
    #headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    headers = {"User-Agent": "Python script"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    data = response.json()
    total_cve = data.get("totalResults", 0)
    print(f"Total numbero of CVE in NVD: {total_cve}")
    return total_cve

K = get_total_nvd_cve()

def calculate_ET(AM,NM,V):
    sum_term = 0
    for tries in range(2, V - AM + 2):
        prod_term = 1
        for i in range(2, tries + 1):
            prod_term *= (NM - i + 2) / (V - i + 1)
        sum_term += tries * prod_term
    ET = (AM / V) * (1 + sum_term)
    return ET



def calculate_TTC(V, M, K, AM, NM):

    #P1 = 1 - ex(-V * (M / K))
    P1 = 1 - math.exp(-V * (M / K))

    #u = (1-s)^V
    u = (1 - s) ** V

    #t2 = 5.8 * ET
    ET = calculate_ET(AM, NM, V)
    t2 = 5.8 * ET

    #t3 = ((1/s) - 0.5) * 30.42 + 5.8
    t3 = ((1 / s) - 0.5) * 30.42 + 5.8

    #TTC 
    T = t1 * P1 + t2 * (1 - P1) * (1 - u) + t3 * u * (1 - P1)
    return T


with open(NETWORK_FILE, "r") as f:
    network_data = json.load(f)

#list of TTC
ttc_rows = []

for device in network_data["devices"]:
    ip = device["ipaddress"]
    
    cve_set = set()
    for iface in device.get("network_interfaces", []):
        #each port can have multiple services
        for port in iface.get("ports", []):
            #iterate over services
            for svc in port.get("services", []):
                #each service can have multiple CVEs
                for cve in svc.get("cve_list", []):
                    #skip CVE null or empty
                    if not cve:
                        continue
                    cvestr = str(cve).strip()
                    if not cvestr:
                        continue
                    #skip CVE-any (some services have CVE-any to indicate generic vulnerability)
                    if cvestr.lower() == "cve-any":
                        continue
                    cve_set.add(cvestr)
    cve_list = sorted(list(cve_set))

    #if the device have no CVEs
    if not cve_list:
        M_count = 0 #number of known exploits
        M_expected = 0.0 #probability of exploits epss
    else:
        #counting how many CVEs are in KEV list
        M_count = sum(1 for c in cve_list if c in kev_set)
        #call EPSS API to get the probabilities that each CVE will be exploited
        epss_map = batch_epss_query(cve_list)
        #M-expected is the sum of the probabilities EPSS (estimation of the number of CVEs that can be exploited)
        M_expected = sum(epss_map.get(c, 0.0) for c in cve_list)

    M_hybrid = max(M_count, M_expected)  # o M_expected, o M_count, a seconda del modello

    print(f"\nunique vulns for device {ip}: {cve_set}\n")
    V = len(cve_set)

    if V == 0:
        ttc_value = 999
    else:
        M = M_hybrid  #vulns contained in KEV
        AM = int(s * M) #accessible exploits = level of the attacker (intermediate) * available exploits
        NM = V - AM
        ttc_value = calculate_TTC(V, M, K, AM, NM)
    ttc_rows.append({"Device": ip, "TTC": round(ttc_value, 2)})

#write the results
with open(TTC_CSV_FILE, "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["Device", "TTC"])
    writer.writeheader()
    writer.writerows(ttc_rows)

print(f"TTC computation done! Saving the results in {TTC_CSV_FILE}")