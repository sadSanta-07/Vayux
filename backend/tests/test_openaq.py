import urllib.request
import json
import ssl
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# Test OpenAQ for Delhi stations
try:
    url = "https://api.openaq.org/v3/locations?bbox=76.8,28.3,77.5,28.9&limit=10"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, context=ctx, timeout=8)
    data = json.loads(res.read().decode())
    print("OpenAQ Locations in Delhi NCR:", len(data.get("results", [])))
    for loc in data.get("results", [])[:5]:
        print(f"- {loc.get('name')}: id={loc.get('id')}, sensors={len(loc.get('sensors', []))}")
except Exception as e:
    print("OpenAQ Error:", e)

# Test Open-Meteo Air Quality API for Delhi coordinates
try:
    url_aq = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=28.6139&longitude=77.2090&current=pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone,european_aqi,us_aqi&timezone=Asia/Kolkata"
    req = urllib.request.Request(url_aq, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, context=ctx, timeout=8)
    aq_data = json.loads(res.read().decode()).get("current", {})
    print("\n[OPEN-METEO AIR QUALITY SATELLITE + CAMS REANALYSIS (DELHI)]")
    print(f"  • Current PM2.5: {aq_data.get('pm2_5')} µg/m³")
    print(f"  • Current PM10: {aq_data.get('pm10')} µg/m³")
    print(f"  • Current NO2: {aq_data.get('nitrogen_dioxide')} µg/m³")
    print(f"  • Current SO2: {aq_data.get('sulphur_dioxide')} µg/m³")
    print(f"  • Current CO: {aq_data.get('carbon_monoxide')} µg/m³")
    print(f"  • Current O3: {aq_data.get('ozone')} µg/m³")
    print(f"  • US AQI: {aq_data.get('us_aqi')}")
    print(f"  • European AQI: {aq_data.get('european_aqi')}")
except Exception as e:
    print("Open-Meteo Air Quality Error:", e)
