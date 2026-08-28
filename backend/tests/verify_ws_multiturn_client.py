import asyncio
import json
import os
import sys
import websockets
from dotenv import load_dotenv

load_dotenv()

async def test_websocket_multiturn_client():
    ws_url = "ws://localhost:8000/ws/jarvis-live"
    print(f"[TEST CLIENT] Connecting to WebSocket: {ws_url}...", flush=True)

    try:
        async with websockets.connect(ws_url) as ws:
            # 1. Wait for server status
            msg = await ws.recv()
            status = json.loads(msg)
            print(f"[CONNECTED] Server Ready: Assistant={status.get('assistant')}, VoiceModel={status.get('voice_model')}\n", flush=True)

            test_turns = [
                ("TURN 1: Temperature & Weather", "What is the live temperature and weather in Delhi?"),
                ("TURN 2: Stubble Fires", "How many active crop stubble fires are detected upwind?"),
                ("TURN 3: 72h Forecast", "What is the 72 hour air quality forecast for Delhi?"),
                ("TURN 4: Policy Simulation", "Simulate a 50% reduction in vehicular traffic.")
            ]

            for turn_label, query in test_turns:
                print(f"[{turn_label}] Sending: '{query}'", flush=True)
                await ws.send(json.dumps({"type": "text_query", "text": query}))

                audio_bytes = 0
                transcripts = []
                turn_finished = False

                # Receive streaming responses until turn_complete or 15s timeout
                start_time = asyncio.get_event_loop().time()
                while asyncio.get_event_loop().time() - start_time < 15.0:
                    try:
                        res = await asyncio.wait_for(ws.recv(), timeout=6.0)
                        if isinstance(res, bytes):
                            audio_bytes += len(res)
                        elif isinstance(res, str):
                            data = json.loads(res)
                            if data.get("type") == "transcript":
                                transcripts.append(data.get("text", ""))
                            elif data.get("type") == "turn_complete":
                                turn_finished = True
                                break
                    except asyncio.TimeoutError:
                        if audio_bytes > 0:
                            turn_finished = True
                            break

                print(f"  -> Audio Streamed: {audio_bytes} bytes")
                if transcripts:
                    print(f"  -> Text Transcript: {' '.join(transcripts[:1])[:100]}...")
                
                if audio_bytes == 0:
                    print(f"[FAIL] {turn_label} received 0 audio bytes!", flush=True)
                    return False

                print(f"  -> [{turn_label} PASSED]\n", flush=True)
                await asyncio.sleep(1.0)

            print("[ALL 4 MULTI-TURN CONVERSATIONS VERIFIED OVER WEBSOCKET WITH AUDIO!]")
            return True

    except Exception as e:
        print(f"[FAIL] WebSocket test exception: {e}", flush=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_websocket_multiturn_client())
    sys.exit(0 if success else 1)
