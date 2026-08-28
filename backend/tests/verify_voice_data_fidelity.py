import asyncio
import json
import os
import sys
import websockets
from dotenv import load_dotenv

load_dotenv()

async def test_voice_data_fidelity():
    ws_url = "ws://localhost:8000/ws/jarvis-live"
    print(f"[TEST FIDELITY] Connecting to WebSocket: {ws_url}...", flush=True)

    async with websockets.connect(ws_url) as ws:
        msg = await ws.recv()
        status = json.loads(msg)
        print(f"[CONNECTED] Assistant: {status.get('assistant')}, VoiceModel: {status.get('voice_model')}\n", flush=True)

        # 1. Ask for live AQI & Weather
        query = "What is the current AQI and weather in Delhi NCR?"
        print(f"[TURN 1] Sending: '{query}'", flush=True)
        await ws.send(json.dumps({"type": "text_query", "text": query}))

        audio_bytes = 0
        transcript_parts = []
        turn_done = False

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < 15.0:
            try:
                res = await asyncio.wait_for(ws.recv(), timeout=6.0)
                if isinstance(res, bytes):
                    audio_bytes += len(res)
                elif isinstance(res, str):
                    data = json.loads(res)
                    if data.get("type") == "transcript":
                        transcript_parts.append(data.get("text", ""))
                    elif data.get("type") == "turn_complete":
                        turn_done = True
                        break
            except asyncio.TimeoutError:
                if audio_bytes > 0:
                    break

        transcript_full = " ".join(transcript_parts)
        print(f"[TURN 1 RESULT] Audio: {audio_bytes} bytes")
        print(f"[TURN 1 TRANSCRIPT] {transcript_full[:150]}...")
        assert audio_bytes > 0, "Turn 1 received 0 audio bytes!"

        await asyncio.sleep(1.0)

        # 2. Turn 2: Follow-up question
        query_2 = "What is the 72 hour air quality peak forecast?"
        print(f"\n[TURN 2] Sending: '{query_2}'", flush=True)
        await ws.send(json.dumps({"type": "text_query", "text": query_2}))

        audio_bytes_2 = 0
        transcript_parts_2 = []

        start = asyncio.get_event_loop().time()
        while asyncio.get_event_loop().time() - start < 20.0:
            try:
                res = await asyncio.wait_for(ws.recv(), timeout=12.0)
                if isinstance(res, bytes):
                    audio_bytes_2 += len(res)
                elif isinstance(res, str):
                    data = json.loads(res)
                    if data.get("type") == "transcript":
                        transcript_parts_2.append(data.get("text", ""))
                    elif data.get("type") == "turn_complete":
                        break
            except asyncio.TimeoutError:
                if audio_bytes_2 > 0:
                    break

        transcript_full_2 = " ".join(transcript_parts_2)
        print(f"[TURN 2 RESULT] Audio: {audio_bytes_2} bytes")
        print(f"[TURN 2 TRANSCRIPT] {transcript_full_2[:150]}...")
        assert audio_bytes_2 > 0, "Turn 2 received 0 audio bytes!"

        print("\n[ALL MULTI-TURN DATA FIDELITY TESTS PASSED!]")
        return True

if __name__ == "__main__":
    success = asyncio.run(test_voice_data_fidelity())
    sys.exit(0 if success else 1)
