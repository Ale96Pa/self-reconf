
import subprocess
import json
import xmltodict
import requests
import time
import re
from pathlib import Path

NVD_API = "https://services.nvd.nist.gov/rest/json/cves/2.0"
# API_KEY = None

def run_nmap(target_range, outfile="scan.xml"):
    """start nmap in service/version detection mode + vulners script (output XML)."""
    cmd = ["nmap", "-sV", "--script", "vulners", "-oX", outfile, target_range]
    print(" ".join(cmd))
    subprocess.run(cmd, check=True)
    return outfile


def _ensure_list(x):
    """Utility: if x is not a list, convert it to a list; if None, return empty list."""
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def parse_nmap(xmlfile):
    """
    Converts nmap XML output into a list of devices with their services and CVEs.
    Each device is represented as a dictionary:
    [
      {
        "hostname": "...",
        "ipaddress": "...",
        "macaddress": "...",
        "network_interfaces": [
           {
             "name": "eth0",
             "ipaddress": "...",
             "ports": [
               {
                 "port": "22",
                 "protocol": "tcp",
                 "services": [
                   {
                     "name": "ssh",
                     "cpe_list": [...],
                     "cve_list": [...]
                   }
                 ]
               }, ...
             ]
           }
        ]
      }, ...
    ]
    """
    with open(xmlfile, "r") as f:
        raw = xmltodict.parse(f.read())

    hosts_info = []
    # xmltodict can return a single dict or a list depending on number of hosts
    raw_hosts = raw["nmaprun"].get("host", [])
    raw_hosts = _ensure_list(raw_hosts)

    for host in raw_hosts:
        # skip hosts down
        if host.get("status", {}).get("@state") == "down":
            continue

        #addresses
        ipaddr = None
        macaddr = None
        addrs = host.get("address", [])
        addrs = _ensure_list(addrs)
        for addr in addrs:
            t = addr.get("@addrtype", "")
            if t == "ipv4":
                ipaddr = addr.get("@addr")
            elif t == "mac":
                macaddr = addr.get("@addr")

        #ports and services
        ports_block = host.get("ports", {})
        ports_raw = ports_block.get("port", [])
        ports_raw = _ensure_list(ports_raw)

        ports = []
        for p in ports_raw:
            #some ports may not have a service
            service = p.get("service", {}) or {}
            #managing cpe_list which can be a single string or a list
            cpes = []
            if "cpe" in service:
                cpe_raw = service.get("cpe")
                cpes = _ensure_list(cpe_raw)
            #extracting CVEs from vulners script output
            cve_list = []
        
            scripts = p.get("script", [])
            scripts = _ensure_list(scripts)
            for s in scripts:
                if s.get("@id") in ("vulners", "vulners.nse"):
                    output = s.get("@output", "") or ""
                    #extract CVE identifiers using regex
                    found = re.findall(r"(CVE-\d{4}-\d+)", output)
                    for cve in found:
                        if cve not in cve_list:
                            cve_list.append(cve)

            #building service entry
            svc_entry = {
                "name": service.get("@name", service.get("name", "unknown")),
                "cpe_list": cpes,
                "cve_list": cve_list
            }

            ports.append({
                "port": p.get("@portid"),
                "protocol": p.get("@protocol"),
                "services": [svc_entry]
            })

        hosts_info.append({
            "hostname": ipaddr,
            "ipaddress": ipaddr,
            "macaddress": macaddr or "00:00:00:00:00:00",
            "network_interfaces": [{
                "name": "eth0",
                "ipaddress": ipaddr,
                "ports": ports
            }]
        })

    return hosts_info


def get_dumb_byID(cveList, seen_vulns):
    """
    for each cveID in cveList, query NVD API to get vulnerability details.
    seen_vulns is a set of already processed CVE IDs to avoid duplicate queries.
    """
    dump_cve = []
    headers = {'content-type': 'application/json'}
    for cveID in cveList:
        if cveID in seen_vulns:  #if already seen, skip
            continue
        params = {"cveID": cveID}
        #rate limiting 
        time.sleep(6)
        try:
            response = requests.get(NVD_API, params=params, headers=headers, timeout=30)
        except requests.RequestException as e:
            print(f"[!] Error HTTP for {cveID}: {e}")
            continue
        if response.status_code == 200:
            jsonResponse = response.json()
            for cve in jsonResponse.get("vulnerabilities", []):
                cid = cve.get("cve", {}).get("id")
                if cid and cid not in seen_vulns:
                    dump_cve.append(cve["cve"])
                    seen_vulns.add(cid)
        else:
            print(f"[!] NVD API returned {response.status_code} for {cveID}")
    return dump_cve


def build_attackgraph_json(devices):
    #generating structure for attack graph JSON
    edges = []
    vulnerabilities = []
    seen_vulns = set()

    #links: full mesh 
    ips = [d["ipaddress"] for d in devices if d.get("ipaddress")]
    for src in ips:
        for dst in ips:
            if src != dst:
                edges.append({"host_link": [src, dst]})

    #associate vulnerabilities to devices based on their services' CVEs
    for dev in devices:
        for iface in dev.get("network_interfaces", []):
            for port in iface.get("ports", []):
                for svc in port.get("services", []):
                    #empty cve_list check
                    svc_cve_list = svc.get("cve_list", [])
                    #call NVD API to get vulnerability details only for new CVEs
                    new_vulns = get_dumb_byID(svc_cve_list, seen_vulns)
                    vulnerabilities.extend(new_vulns)

                    #update the service's cve_list
                    #avoid querying NVD multiple times for same CVE
                    svc["cve_list"] = list(dict.fromkeys(svc_cve_list))

    return {
        "devices": devices,
        "vulnerabilities": vulnerabilities,
        "edges": edges
    }

#different output filename based on the group of machines we are analyzing (replicas or candidates)
def choose_output_filename(target_range):
    #Return the name of the json file based on the scanned IP range
    
    #normalize target range string by removing spaces
    tr = target_range.replace(" ", "")

    # Replicas (110–118)
    if "110-118" in tr:
        return "MyNetwork.json"

    # Candidates (50–61)
    if "50-61" in tr or "50-61" in tr:
        return "MyCandidates.json"

    # Default if not matched
    return "ScanOutput.json"


if __name__ == "__main__":
    #9 or 6 hosts in the range
    target = "192.168.56.50-61"
    xmlfile = run_nmap(target)
    devices = parse_nmap(xmlfile)
    result = build_attackgraph_json(devices)

    #save to JSON file
    outfile = choose_output_filename(target)
    with open(outfile, "w") as f:
        json.dump(result, f, indent=2)
    print(f"File {outfile} creato!")
