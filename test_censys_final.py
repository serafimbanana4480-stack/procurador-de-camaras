"""Test Censys direct API with the provided key."""
import os
import requests
import sys

api_id = os.environ.get("CENSYS_API_ID", "")
api_secret = ""

print(f"[*] API ID: {api_id[:20]}...")
print(f"[*] API Secret: '{api_secret}'")
print()

# Try 1: Basic auth with ID + empty secret
url = "https://search.censys.io/api/v2/hosts/search"
params = {"q": "services.service_name: RTSP", "per_page": 3}

print("[1] Basic auth (ID, '')...")
r = requests.get(url, auth=(api_id, api_secret), params=params, timeout=15)
print(f"    Status: {r.status_code}")
if r.status_code == 200:
    hits = r.json().get("result", {}).get("hits", [])
    print(f"    Found {len(hits)} cameras")
    for h in hits[:3]:
        print(f"      IP: {h.get('ip')}")
else:
    print(f"    Error: {r.text[:200]}")

# Try 2: No auth (maybe public search)
print()
print("[2] No auth (public)...")
r2 = requests.get(url, params=params, timeout=15)
print(f"    Status: {r2.status_code}")
if r2.status_code == 200:
    hits = r2.json().get("result", {}).get("hits", [])
    print(f"    Found {len(hits)} cameras")
else:
    print(f"    Error: {r2.text[:200]}")

# Try 3: With the key as bearer token
print()
print("[3] Bearer token...")
headers = {"Authorization": f"Bearer {api_id}"}
r3 = requests.get(url, headers=headers, params=params, timeout=15)
print(f"    Status: {r3.status_code}")
if r3.status_code == 200:
    hits = r3.json().get("result", {}).get("hits", [])
    print(f"    Found {len(hits)} cameras")
else:
    print(f"    Error: {r3.text[:200]}")

# Try 4: Censys v1 API endpoint
print()
print("[4] Censys v1 API...")
url_v1 = "https://search.censys.io/api/v1/hosts/search"
r4 = requests.get(url_v1, auth=(api_id, api_secret), params=params, timeout=15)
print(f"    Status: {r4.status_code}")
if r4.status_code == 200:
    hits = r4.json().get("results", [])
    print(f"    Found {len(hits)} cameras")
else:
    print(f"    Error: {r4.text[:200]}")

# Try 5: Just search the web version
print()
print("[5] Web search...")
url_web = f"https://search.censys.io/api/v2/hosts/search?q=services.service_name: RTSP&per_page=3"
resp = requests.get(url_web, timeout=15)
print(f"    Status: {resp.status_code}")
print(f"    Body: {resp.text[:200]}")
