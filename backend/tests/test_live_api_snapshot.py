import urllib.request
import json
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

res = urllib.request.urlopen('http://localhost:3000/api/aqi')
data = json.loads(res.read().decode())
stations = data['stations']['features']
print(f"Total reporting CAAQMS stations: {len(stations)}")
aqis = [s['properties']['aqi'] for s in stations if s.get('properties', {}).get('aqi') is not None]
avg_aqi = round(sum(aqis) / len(aqis))
print(f"Delhi NCR Regional Baseline AQI: {avg_aqi}")

print("\nSample Station Real-Time Telemetry:")
for s in stations[:6]:
    p = s['properties']
    print(f"  • {p['station']}:")
    print(f"      AQI: {p['aqi']} ({p['category']}) | Dominant: {p.get('dominantPollutant')}")
    print(f"      PM2.5: {p['pm25']} µg/m³ | PM10: {p['pm10']} µg/m³")
    print(f"      Temp: {p.get('temperature')}°C | Humidity: {p.get('humidity')}% | Wind: {p.get('windSpeed')} m/s\n")
