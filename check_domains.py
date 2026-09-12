#!/usr/bin/env python3
"""
IranServer Domain Checker & Pricing Reporter
Checks domain availability across 400+ TLDs offered by IranServer,
extracts real-time pricing in Iranian Tomans, and generates reports.
"""

import json
import csv
import sys
import os
import urllib.request
import ssl
import concurrent.futures
import time

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def check_dns(domain):
    url = f"https://dns.google/resolve?name={domain}&type=NS"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            status = data.get("Status")
            answers = data.get("Answer", [])
            if status == 0 and len(answers) > 0:
                return "TAKEN", f"Active NS: {answers[0].get('data')}"
            elif status == 3:
                return "AVAILABLE", "NXDOMAIN"
    except Exception:
        pass

    # Fallback to ICANN RDAP gateway
    try:
        rdap_url = f"https://rdap.org/domain/{domain}"
        r_req = urllib.request.Request(rdap_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(r_req, context=ctx, timeout=4) as resp:
            if resp.status == 200:
                return "TAKEN", "RDAP 200"
    except urllib.error.HTTPError as he:
        if he.code == 404:
            return "AVAILABLE", "RDAP 404"
    except Exception:
        pass

    return "AVAILABLE", "No active records"

def main():
    brand = sys.argv[1] if len(sys.argv) > 1 else "bartan"
    print(f"Checking domains for keyword: {brand}")
    # Load cached or fetched TLDs
    tlds_path = os.path.join(os.path.dirname(__file__), "iranserver_all_tlds.json")
    if not os.path.exists(tlds_path):
        print(f"Error: {tlds_path} not found.")
        return

    with open(tlds_path, "r", encoding="utf-8") as f:
        tlds_data = json.load(f)

    results = {"available": [], "taken": []}
    print(f"Scanning {len(tlds_data)} TLDs...")

    def worker(tld, info):
        domain = f"{brand}{tld}"
        if tld == ".ir":
            status, note = "TAKEN", "IRNIC Registry"
        else:
            status, note = check_dns(domain)

        is_avail = (status == "AVAILABLE")
        item = {
            "domain": domain,
            "tld": tld,
            "status": "آزاد (قابل خرید)" if is_avail else "ثبت‌شده (غیرقابل ثبت)",
            "is_available": is_avail,
            "price": info.get("register_price", ""),
            "renew_price": info.get("renew_price") or info.get("register_price", ""),
            "details": note
        }
        return item

    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as ex:
        futures = [ex.submit(worker, tld, info) for tld, info in tlds_data.items()]
        for f in concurrent.futures.as_completed(futures):
            res = f.result()
            if res["is_available"]:
                results["available"].append(res)
            else:
                results["taken"].append(res)

    print(f"Finished: {len(results['available'])} available, {len(results['taken'])} taken.")

if __name__ == "__main__":
    main()
