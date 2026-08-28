import urllib.request
import json
import ssl
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

url = "https://api.waqi.info/search/?keyword=delhi&token=demo"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
res = urllib.request.urlopen(req, context=ctx, timeout=8)
data = json.loads(res.read().decode())
results = data.get("data", [])
print(f"Total WAQI Stations found for Delhi: {len(results)}\n")
for r in results[:15]:
    st = r.get("station", {})
    print(f"Station: {st.get('name')}")
    print(f"  AQI: {r.get('aqi')}")
    print(f"  Time: {r.get('time', {}).get('stime')}")
    print(f"  Coordinates: {st.get('geo')}\n")
