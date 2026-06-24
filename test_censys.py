"""Teste rápido da API Censys."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

API_ID = os.environ.get("CENSYS_API_ID", "Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR")

print(f"[*] API ID: {API_ID[:20]}...")
print(f"[*] Python: {sys.version}")

try:
    from censys.search import CensysHosts
    print("[*] CensysHosts imported OK")
    
    c = CensysHosts(api_id=API_ID, api_secret="")
    print("[*] CensysHosts initialized OK")
    
    query = "services.service_name: RTSP and location.country_code: PT"
    print(f"[*] Query: {query}")
    
    results = list(c.search(query, per_page=10))
    print(f"[+] Encontrados {len(results)} resultados")
    
    for r in results[:5]:
        ip = r.get("ip", "?")
        loc = r.get("location", {})
        country = loc.get("country", "?")
        city = loc.get("city", "?")
        services = r.get("services", [])
        rtsp = next((s for s in services if s.get("service_name") == "RTSP"), None)
        if rtsp:
            port = rtsp.get("port", "?")
            print(f"  [+] {ip}:{port} - {country}, {city}")
        else:
            print(f"  [-] {ip} - {country}, {city} (no RTSP service)")
            
except Exception as e:
    print(f"[-] Erro: {e}")
    import traceback
    traceback.print_exc()
