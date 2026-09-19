"""
NetSage AI - Deterministic Rule Checker
Runs independent, non-AI checks against the structured config facts captured
for each case in data/cases.csv. These checks catch the "obvious" config
mistakes the AI diagnosis should also have caught, and give the dashboard an
AI-agreement signal that doesn't depend on the AI being right.

Checks implemented (as required by the project spec):
  1. duplicate_ip        - a host/interface IP collides with another device
  2. wrong_mask           - host subnet mask does not match the router's mask
                             on the same segment
  3. gateway_mismatch     - host's configured gateway is not the router's
                             real interface IP on that segment
  4. interface_down       - the relevant interface is down/down or
                             administratively down
  5. missing_vlan         - a port is assigned to a VLAN that doesn't exist
                             on the switch
  6. missing_route        - no route exists to the destination network

Can run "before or after" the AI diagnosis: it only reads the structured
config columns, never the AI's output, so it's a fully independent check.
"""
import csv
import ipaddress

IN_PATH = "/home/claude/netsage_ai/data/cases.csv"
OUT_PATH = "/home/claude/netsage_ai/data/rule_checker_results.csv"


def is_valid_ip(s):
    try:
        ipaddress.ip_address(s)
        return True
    except (ValueError, TypeError):
        return False


def check_duplicate_ip(row):
    return row.get("duplicate_ip_flag", "False").strip() == "True"


def check_wrong_mask(row):
    hm, rm = row.get("host_mask"), row.get("router_interface_mask")
    if hm in ("n/a", "", None) or rm in ("n/a", "", None):
        return False
    return hm != rm


def check_gateway_mismatch(row):
    gw, real = row.get("gateway_ip_configured"), row.get("router_interface_ip")
    if gw in ("n/a", "", None) or real in ("n/a", "", None):
        return False
    if gw == "0.0.0.0":  # host never got a gateway at all (e.g. DHCP failure)
        return False
    return gw != real


def check_interface_down(row):
    status = (row.get("interface_status") or "").strip().lower()
    return status not in ("up/up", "n/a", "")


def check_missing_vlan(row):
    assigned = row.get("vlan_assigned_on_port")
    exists = row.get("vlan_exists_on_switch")
    if assigned in ("n/a", "", None) or exists in ("n/a", "", None):
        return False
    if exists == "none":
        return True
    return assigned != exists


def check_missing_route(row):
    return (row.get("route_to_dest_present") or "").strip() == "False"


CHECKS = [
    ("duplicate_ip", check_duplicate_ip),
    ("wrong_mask", check_wrong_mask),
    ("gateway_mismatch", check_gateway_mismatch),
    ("interface_down", check_interface_down),
    ("missing_vlan", check_missing_vlan),
    ("missing_route", check_missing_route),
]


def run():
    with open(IN_PATH, newline="") as f:
        rows = list(csv.DictReader(f))

    out_fields = ["case_id", "category"] + [c[0] for c in CHECKS] + ["flags_raised", "clean"]
    results = []
    for row in rows:
        result = {"case_id": row["case_id"], "category": row["category"]}
        flags = []
        for name, fn in CHECKS:
            hit = fn(row)
            result[name] = hit
            if hit:
                flags.append(name)
        result["flags_raised"] = ";".join(flags) if flags else ""
        result["clean"] = len(flags) == 0
        results.append(result)

    with open(OUT_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(results)

    flagged = [r for r in results if not r["clean"]]
    print(f"Checked {len(results)} cases. {len(flagged)} raised at least one deterministic flag.")
    for r in flagged:
        print(f"  {r['case_id']} ({r['category']}): {r['flags_raised']}")
    return results


if __name__ == "__main__":
    run()
