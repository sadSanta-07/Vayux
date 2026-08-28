import urllib.request
import json

url = "https://api.open-meteo.com/v1/forecast?latitude=28.6139&longitude=77.2090&hourly=temperature_2m,relative_humidity_2m,wind_speed_10m,boundary_layer_height&forecast_days=3"
res = urllib.request.urlopen(url)
data = json.loads(res.read().decode())
hourly = data.get("hourly", {})
temps = hourly.get("temperature_2m", [])
humidity = hourly.get("relative_humidity_2m", [])
winds = hourly.get("wind_speed_10m", [])
pblhs = hourly.get("boundary_layer_height", [])
times = hourly.get("time", [])

print(f"Total hourly points: {len(times)}")
print(f"Temperature range: Min={min(temps)}°C, Max={max(temps)}°C, Current={temps[0]}°C")
print(f"First 12h temps: {temps[:12]}")
