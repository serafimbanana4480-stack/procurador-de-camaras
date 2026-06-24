"""Check Censys library version and API requirements."""


# Check init signature
from censys.search import CensysHosts
import inspect
sig = inspect.signature(CensysHosts.__init__)
print(f"Signature: {sig}")

# Check if single key works
print("\nTrying with single key...")
try:
    c = CensysHosts(api_id="Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR", api_secret="")
    print("OK - initialized")
    results = list(c.search("services.service_name: RTSP", per_page=3))
    print(f"Found {len(results)} results")
except Exception as e:
    print(f"Error: {e}")
    
    # Try with secret same as id
    print("\nTrying with api_secret=api_id...")
    try:
        c = CensysHosts(api_id="Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR", api_secret="Qtdg3uaj_m2DUPXzwr5jQkFr64brGDyuR")
        results = list(c.search("services.service_name: RTSP", per_page=3))
        print(f"Found {len(results)} results")
    except Exception as e2:
        print(f"Error: {e2}")
