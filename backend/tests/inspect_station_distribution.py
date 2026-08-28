import urllib.request
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

res = urllib.request.urlopen('http://localhost:3000/api/aqi')
data = json.loads(res.read().decode())
stations = data['stations']['features']
aqis = [s['properties']['aqi'] for s in stations if s.get('properties', {}).get('aqi') is not None]

print(f"Total Reporting CAAQMS Stations: {len(stations)}")
print(f"Regional NCR Range: Min AQI = {min(aqis)} | Max AQI = {max(aqis)} | Regional Average = {round(sum(aqis)/len(aqis))}\n")

# Distribution
cats = {}
for s in stations:
    c = s['properties'].get('category', 'Unknown')
    cats[c] = cats.get(c, 0) + 1
print(f"Air Quality Category Breakdown across NCR: {cats}\n")

sorted_stations = sorted(stations, key=lambda s: s['properties'].get('aqi', 0))

print("Cleanest/Green Belt Stations in Delhi NCR:")
for s in sorted_stations[:4]:
    p = s['properties']
    print(f"  • {p['station']}: AQI {p['aqi']} ({p['category']}) | PM2.5: {p['pm25']} µg/m³, PM10: {p['pm10']} µg/m³")

print("\nDense Traffic / Industrial / Hotspot Stations in Delhi NCR:")
for s in sorted_stations[-4:]:
    p = s['properties']
    print(f"  • {p['station']}: AQI {p['aqi']} ({p['category']}) | PM2.5: {p['pm25']} µg/m³, PM10: {p['pm10']} µg/m³")
