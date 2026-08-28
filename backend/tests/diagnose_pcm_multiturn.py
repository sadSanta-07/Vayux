import asyncio
import os
import sys
import numpy as np
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

def generate_pcm_audio(freq=440.0, duration_sec=1.5, sample_rate=16000):
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    carrier = np.sin(2 * np.pi * freq * t)
    modulator = 0.5 * (1 + np.sin(2 * np.pi * 3.0 * t))
    signal = (carrier * modulator * 0.5 * 32767).astype(np.int16)
    return signal.tobytes()

async def diagnose_multiturn_pcm():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[FAIL] No API key.", flush=True)
        return False

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text="You are VayuVani voice co-pilot. Respond naturally to spoken audio.")]),
        tools=[{"function_declarations": JARVIS_TOOL_DECLARATIONS}]
    )

    model_id = "gemini-2.5-flash-native-audio-latest"
    print(f"[DIAGNOSE] Connecting to {model_id}...", flush=True)

    async with client.aio.live.connect(model=model_id, config=config) as session:
        print("[CONNECTED] Testing Turn 1...", flush=True)

        # Turn 1: Send text or audio
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="What is the weather in Delhi?")]),
            turn_complete=True
        )

        audio_t1 = 0
        async for response in session.receive():
            if response.tool_call:
                for fc in response.tool_call.function_calls:
                    print(f"  [T1 TOOL] {fc.name}", flush=True)
                    res = await execute_jarvis_tool(fc.name, fc.args)
                    await session.send_tool_response(
                        function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                    )
            if response.server_content and response.server_content.model_turn:
                for p in response.server_content.model_turn.parts:
                    if p.inline_data:
                        audio_t1 += len(p.inline_data.data)
            if response.server_content and response.server_content.turn_complete:
                print(f"  [T1 DONE] Received {audio_t1} bytes.", flush=True)
                break

        print("\n[PAUSE] Simulating 2 second silence before Turn 2...", flush=True)
        await asyncio.sleep(2)

        print("[TURN 2] Sending Turn 2 question: 'How about active stubble fires?'...", flush=True)
        # Testing sending turn 2 via send_client_content and PCM stream
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="How about active stubble fires?")]),
            turn_complete=True
        )

        audio_t2 = 0
        t2_received = False
        try:
            # Set a 10s timeout to see if turn 2 responds or hangs
            async def receive_turn2():
                nonlocal audio_t2, t2_received
                async for response in session.receive():
                    if response.tool_call:
                        for fc in response.tool_call.function_calls:
                            print(f"  [T2 TOOL] {fc.name}", flush=True)
                            res = await execute_jarvis_tool(fc.name, fc.args)
                            await session.send_tool_response(
                                function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                            )
                    if response.server_content and response.server_content.model_turn:
                        for p in response.server_content.model_turn.parts:
                            if p.inline_data:
                                audio_t2 += len(p.inline_data.data)
                    if response.server_content and response.server_content.turn_complete:
                        print(f"  [T2 DONE] Received {audio_t2} bytes.", flush=True)
                        t2_received = True
                        break

            await asyncio.wait_for(receive_turn2(), timeout=12.0)
        except asyncio.TimeoutError:
            print("[FAIL] Turn 2 timed out! Session did not respond on second turn.", flush=True)
            return False

        if t2_received:
            print("[SUCCESS] Turn 2 responded cleanly!", flush=True)
            return True
        return False

if __name__ == "__main__":
    asyncio.run(diagnose_multiturn_pcm())
