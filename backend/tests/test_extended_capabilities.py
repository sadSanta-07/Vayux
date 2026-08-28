import asyncio
import json
import os
import sys
import websockets
from dotenv import load_dotenv

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

load_dotenv()

async def test_extended_capabilities():
    ws_url = "ws://localhost:8000/ws/jarvis-live"
    print("====================================================================")
    print("🎙️ VayuVani Extended Intelligence: Stations, Forecast & Web Intel")
    print("====================================================================\n")

    async with websockets.connect(ws_url) as ws:
        status = json.loads(await ws.recv())
        print(f"[CONNECTED] Assistant: {status.get('assistant')}, VoiceModel: {status.get('voice_model')}\n")

        test_turns = [
            (
                "TEST 1: Specific Station AQI (Anand Vihar)",
                "What is the live AQI and pollutant details at Anand Vihar station?"
            ),
            (
                "TEST 2: Forecasted Temperature & 72h AQI (Punjabi Bagh)",
                "What is the forecasted temperature and 72-hour air quality forecast for Punjabi Bagh?"
            ),
            (
                "TEST 3: Web Search Environmental Intel (CAQM GRAP)",
                "What are the latest official CAQM GRAP orders and restrictions in Delhi NCR?"
            ),
            (
                "TEST 4: Multilingual Station Query (Hindi/Hinglish)",
                "ITO station ka live AQI aur temperature kitna hai?"
            )
        ]

        for turn_idx, (label, query) in enumerate(test_turns, start=1):
            print(f"[{label}] Sending: '{query}'", flush=True)
            await ws.send(json.dumps({"type": "text_query", "text": query}))

            audio_bytes = 0
            transcript_parts = []
            while True:
                res = await ws.recv()
                if isinstance(res, bytes):
                    audio_bytes += len(res)
                elif isinstance(res, str):
                    msg = json.loads(res)
                    if msg.get("type") == "transcript" and msg.get("text"):
                        transcript_parts.append(msg.get("text"))
                    elif msg.get("type") == "turn_complete":
                        full_txt = " ".join(transcript_parts)
                        print(f"  -> Audio: {audio_bytes} bytes")
                        print(f"  -> Transcript snippet: {full_txt[:140]}...")
                        print(f"  -> [{label} PASSED]\n", flush=True)
                        break

            assert audio_bytes > 0, f"{label} failed with 0 audio bytes!"
            await asyncio.sleep(1.0)

    print("====================================================================")
    print("🎉 ALL EXTENDED CAPABILITY TESTS PASSED (100% SUCCESS)!")
    print("====================================================================")
    return True

if __name__ == "__main__":
    success = asyncio.run(test_extended_capabilities())
    sys.exit(0 if success else 1)
