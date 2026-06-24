"""Test Censys API directly via HTTP."""
import os
import requests
import json

API_KEY = os.environ.get("CENSYS_API_ID", "Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR")

print(f"[*] Using API key: {API_KEY[:20]}...")

# Try Censys v2 API (new Platform API)
url = "https://search.censys.io/api/v2/hosts/search"
headers = {
    "Accept": "application/json",
}
params = {
    "q": "services.service_name: RTSP",
    "per_page": 5,
}

print("[*] Trying Basic Auth...")
try:
    r = requests.get(url, auth=(API_KEY, ""), params=params, timeout=10)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        hits = data.get("result", {}).get("hits", [])
        print(f"[+] Found {len(hits)} cameras")
        for h in hits[:3]:
            ip = h.get("ip", "?")
            loc = h.get("location", {})
            print(f"    {ip} - {loc.get('country', '?')}, {loc.get('city', '?')}")
    else:
        print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    Error: {e}")

# Try with Bearer token
print("[*] Trying Bearer Auth...")
try:
    headers["Authorization"] = f"Bearer {API_KEY}"
    r = requests.get(url, headers=headers, params=params, timeout=10)
    print(f"    Status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        hits = data.get("result", {}).get("hits", [])
        print(f"[+] Found {len(hits)} cameras")
    else:
        print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    Error: {e}")

# Also try Shodan style
print("[*] Trying Shodan-style auth...")
try:
    url2 = f"https://search.censys.io/api/v2/hosts/search?q=services.service_name: RTSP&per_page=5&api_id={API_KEY}"
    r = requests.get(url2, timeout=10)
    print(f"    Status: {r.status_code}")
    print(f"    Response: {r.text[:200]}")
except Exception as e:
    print(f"    Error: {e}")
