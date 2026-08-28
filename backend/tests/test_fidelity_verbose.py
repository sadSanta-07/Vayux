import asyncio
import json
import os
import sys
import websockets
from dotenv import load_dotenv

load_dotenv()

async def test_fidelity_verbose():
    ws_url = "ws://localhost:8000/ws/jarvis-live"
    print(f"[TEST] Connecting to: {ws_url}...", flush=True)

    async with websockets.connect(ws_url) as ws:
        # Status
        status = json.loads(await ws.recv())
        print(f"[CONNECTED] Assistant: {status.get('assistant')}\n", flush=True)

        # Turn 1
        print("[TURN 1] Sending AQI & Weather query...", flush=True)
        await ws.send(json.dumps({"type": "text_query", "text": "What is the current AQI and temperature in Delhi NCR?"}))

        t1_audio = 0
        while True:
            res = await ws.recv()
            if isinstance(res, bytes):
                t1_audio += len(res)
            elif isinstance(res, str):
                msg = json.loads(res)
                print(f"  [T1 RECV MSG] {msg}", flush=True)
                if msg.get("type") == "turn_complete":
                    print(f"  [T1 DONE] Audio: {t1_audio} bytes\n", flush=True)
                    break

        # Wait before Turn 2
        print("[WAIT] Waiting 2 seconds...", flush=True)
        await asyncio.sleep(2.0)

        # Turn 2
        print("[TURN 2] Sending 72h forecast query...", flush=True)
        await ws.send(json.dumps({"type": "text_query", "text": "What is the 72 hour air quality peak forecast?"}))

        t2_audio = 0
        while True:
            res = await ws.recv()
            if isinstance(res, bytes):
                t2_audio += len(res)
            elif isinstance(res, str):
                msg = json.loads(res)
                print(f"  [T2 RECV MSG] {msg}", flush=True)
                if msg.get("type") == "turn_complete":
                    print(f"  [T2 DONE] Audio: {t2_audio} bytes\n", flush=True)
                    break

        print("[SUCCESS] Both Turn 1 and Turn 2 completed successfully over WebSocket!")

if __name__ == "__main__":
    asyncio.run(test_fidelity_verbose())
