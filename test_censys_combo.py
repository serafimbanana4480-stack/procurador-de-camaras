"""Test Censys API with different auth combinations."""
import os
import requests

KEY = "Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR"
FULL_KEY = "censys_Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR"

url = "https://search.censys.io/api/v2/hosts/search"
params = {"q": "services.service_name: RTSP", "per_page": 3}

combos = [
    ("ID=key, Secret=key", (KEY, KEY)),
    ("ID='', Secret=key", ("", KEY)),
    ("ID=full_key, Secret=''", (FULL_KEY, "")),
    ("ID=full_key, Secret=full_key", (FULL_KEY, FULL_KEY)),
]

for name, (api_id, api_secret) in combos:
    print(f"[*] Trying: {name}")
    try:
        r = requests.get(url, auth=(api_id, api_secret), params=params, timeout=10)
        print(f"    Status: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            hits = data.get("result", {}).get("hits", [])
            print(f"[+] FOUND! {len(hits)} cameras")
            for h in hits[:3]:
                print(f"    {h.get('ip', '?')}")
            break
        else:
            err = r.json().get("error", "?")
            print(f"    Error: {err}")
    except Exception as e:
        print(f"    Exception: {e}")
