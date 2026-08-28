import urllib.request
import json

res = urllib.request.urlopen('http://localhost:3000/api/aqi')
data = json.loads(res.read().decode())
stations = data['stations']['features']
print('Station count:', len(stations))
for s in stations[:10]:
    p = s['properties']
    print(f"- {p['station']}: AQI={p['aqi']}, PM2.5={p['pm25']}, Temp={p.get('temperature')}, Wind={p.get('windSpeed')}")
