import urllib.request
import json
import ssl
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

coords = [
    ("Central Delhi (Chanakyapuri)", 28.6139, 77.2090),
    ("Anand Vihar, East Delhi", 28.6476, 77.3158),
    ("Punjabi Bagh, West Delhi", 28.6740, 77.1310),
    ("Dwarka Sector 8, South West Delhi", 28.5710, 77.0710),
    ("Rohini, North West Delhi", 28.7325, 77.1190),
    ("Noida Sector 62", 28.6258, 77.3648),
    ("Gurugram Vikas Sadan", 28.4595, 77.0266)
]

print("==========================================================================")
print("🌍 LIVE REAL-WORLD GROUND SENSOR MEASUREMENTS ACROSS DELHI NCR (WAQI/CPCB)")
print("==========================================================================\n")

for label, lat, lon in coords:
    url = f"https://api.waqi.info/feed/geo:{lat};{lon}/?token=demo"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        res = urllib.request.urlopen(req, context=ctx, timeout=6)
        data = json.loads(res.read().decode()).get("data", {})
        city = data.get("city", {}).get("name")
        aqi = data.get("aqi")
        iaqi = data.get("iaqi", {})
        pm25 = iaqi.get("pm25", {}).get("v")
        pm10 = iaqi.get("pm10", {}).get("v")
        t = iaqi.get("t", {}).get("v")
        h = iaqi.get("h", {}).get("v")
        w = iaqi.get("w", {}).get("v")
        print(f"📍 {label}:")
        print(f"   • Station Name: {city}")
        print(f"   • Live AQI: {aqi}")
        print(f"   • Live PM2.5: {pm25} µg/m³ | PM10: {pm10} µg/m³")
        print(f"   • Ground Sensor Weather: Temp={t}°C, Humidity={h}%, Wind={w} m/s\n")
    except Exception as e:
        print(f"📍 {label}: Error ({e})\n")
