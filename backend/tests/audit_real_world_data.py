import urllib.request
import json
import ssl
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

print("=================================================================")
print("🌐 LIVE REAL-WORLD DATA AUDIT: DELHI NCR (WEATHER & AIR QUALITY)")
print("=================================================================\n")

# 1. Open-Meteo Live Weather
try:
    url_wx = "https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&current=temperature_2m,relative_humidity_2m,surface_pressure,wind_speed_10m,wind_direction_10m,boundary_layer_height&timezone=Asia/Kolkata"
    req = urllib.request.Request(url_wx, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, context=ctx)
    wx = json.loads(res.read().decode()).get("current", {})
    print("[1. REAL-WORLD OPEN-METEO WEATHER]")
    print(f"  • Real-Time Temperature: {wx.get('temperature_2m')}°C")
    print(f"  • Real-Time Humidity: {wx.get('relative_humidity_2m')}%")
    print(f"  • Real-Time Wind Speed: {wx.get('wind_speed_10m')} km/h ({round(wx.get('wind_speed_10m', 0)/3.6, 2)} m/s)")
    print(f"  • Real-Time Wind Direction: {wx.get('wind_direction_10m')}°")
    print(f"  • Real-Time Pressure: {wx.get('surface_pressure')} hPa")
    print(f"  • Real-Time Boundary Layer Height: {wx.get('boundary_layer_height')} m\n")
except Exception as e:
    print(f"[Open-Meteo Error] {e}\n")

# 2. WAQI Live Ground CAAQMS Stations in Delhi
stations_to_check = [
    ("Delhi Central (US Embassy / Chanakyapuri)", "https://api.waqi.info/feed/delhi/?token=demo"),
    ("Anand Vihar, Delhi", "https://api.waqi.info/feed/anand-vihar,-delhi/?token=demo"),
    ("Punjabi Bagh, Delhi", "https://api.waqi.info/feed/punjabi-bagh,-delhi/?token=demo"),
    ("ITO, Delhi", "https://api.waqi.info/feed/ito,-delhi/?token=demo"),
    ("R K Puram, Delhi", "https://api.waqi.info/feed/r-k-puram,-delhi/?token=demo")
]

print("[2. REAL-WORLD WAQI / CPCB GROUND STATIONS (LIVE)]")
for name, url in stations_to_check:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        res = urllib.request.urlopen(req, context=ctx, timeout=5)
        data = json.loads(res.read().decode()).get("data", {})
        aqi = data.get("aqi")
        iaqi = data.get("iaqi", {})
        pm25 = iaqi.get("pm25", {}).get("v")
        pm10 = iaqi.get("pm10", {}).get("v")
        time_info = data.get("time", {}).get("s")
        print(f"  • {name}:")
        print(f"      Live AQI: {aqi}")
        print(f"      Live PM2.5: {pm25} µg/m³")
        print(f"      Live PM10: {pm10} µg/m³")
        print(f"      Station Timestamp: {time_info}")
    except Exception as e:
        print(f"  • {name}: Error fetching ({e})")

# 3. Our App's Local API
print("\n[3. OUR VAYUX LOCAL API (http://localhost:3000/api/aqi)]")
try:
    url_local = "http://localhost:3000/api/aqi"
    req = urllib.request.Request(url_local, headers={"User-Agent": "Mozilla/5.0"})
    res = urllib.request.urlopen(req, timeout=5)
    local_data = json.loads(res.read().decode())
    features = local_data.get("stations", {}).get("features", [])
    aqis = [f["properties"]["aqi"] for f in features if f.get("properties", {}).get("aqi") is not None]
    avg_aqi = round(sum(aqis) / len(aqis)) if aqis else 0
    print(f"  • Total Reporting CAAQMS Stations: {len(features)}")
    print(f"  • Delhi NCR Regional Average AQI: {avg_aqi}")
    print(f"  • Sample Station Values:")
    for f in features[:5]:
        p = f["properties"]
        print(f"      - {p['station']}: AQI={p['aqi']} ({p['category']}), PM2.5={p['pm25']}, Temp={p.get('temperature')}°C, Humidity={p.get('humidity')}%")
except Exception as e:
    print(f"[Local API Error] {e}")

# 4. Backend live weather & tools
print("\n[4. OUR BACKEND LIVE DATA (backend/live_data.py)]")
try:
    import asyncio
    from live_data import fetch_live_weather, fetch_live_regional_aqi, fetch_station_details_by_name_or_coords
    
    async def check_backend():
        w = await fetch_live_weather()
        r = await fetch_live_regional_aqi()
        st = await fetch_station_details_by_name_or_coords("Anand Vihar")
        print(f"  • Backend Weather: Temp={w['temperature']}°C, Hum={w['humidity']}%, Wind={w['wind_speed']} m/s, PBLH={w['base_pblh']}m")
        print(f"  • Backend Regional AQI: {r['regional_aqi']} ({r['category']}) across {r['total_reporting_stations']} stations")
        print(f"  • Backend Anand Vihar Lookup: AQI={st.get('aqi')}, PM2.5={st.get('pollutants', {}).get('pm25')}, Temp={st.get('local_weather', {}).get('temperature')}°C")

    asyncio.run(check_backend())
except Exception as e:
    print(f"[Backend Error] {e}")
