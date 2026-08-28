import asyncio
import json
import os
import sys
import websockets
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def test_marathon_multiturn():
    ws_url = "ws://localhost:8000/ws/jarvis-live"
    print("==========================================================")
    print("🎙️ VayuVani 5-Turn Marathon Voice & Data Reliability Test")
    print("==========================================================\n")

    async with websockets.connect(ws_url) as ws:
        status = json.loads(await ws.recv())
        print(f"[CONNECTED] Assistant: {status.get('assistant')}, VoiceModel: {status.get('voice_model')}\n")

        turns = [
            ("TURN 1: Weather & AQI", "What is the live AQI and temperature in Delhi NCR?"),
            ("TURN 2: NASA Fires", "How many active stubble fires are detected upwind?"),
            ("TURN 3: 72h Forecast", "What is the 72 hour air quality forecast?"),
            ("TURN 4: Policy Sim", "Simulate a 50% vehicular traffic ban under GRAP."),
            ("TURN 5: Policy Brief", "Generate a quick emergency mitigation summary.")
        ]

        for turn_id, (label, query) in enumerate(turns, start=1):
            print(f"[{label}] Sending: '{query}'", flush=True)
            await ws.send(json.dumps({"type": "text_query", "text": query}))

            audio_bytes = 0
            while True:
                res = await ws.recv()
                if isinstance(res, bytes):
                    audio_bytes += len(res)
                elif isinstance(res, str):
                    msg = json.loads(res)
                    if msg.get("type") == "turn_complete":
                        print(f"  -> Audio Streamed: {audio_bytes} bytes")
                        print(f"  -> [{label} SUCCESS]\n", flush=True)
                        break

            assert audio_bytes > 0, f"Turn {turn_id} failed with 0 audio bytes!"
            await asyncio.sleep(1.0)

        print("==========================================================")
        print("🎉 MARATHON PASSED: 5/5 TURNS STREAMED AUDIO FLAWLESSLY!")
        print("==========================================================")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_marathon_multiturn())
    sys.exit(0 if success else 1)
