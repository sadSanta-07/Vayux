import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

async def test_live_session_turns():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text="You are VayuVani voice co-pilot. Keep replies short.")]),
        tools=[{"function_declarations": JARVIS_TOOL_DECLARATIONS}]
    )

    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        print("Connected.")

        async def send_worker():
            turns = [
                "What is the live weather in Delhi?",
                "What is the 72 hour air quality forecast?",
                "How many stubble fires are there?"
            ]
            for t in turns:
                print(f"\n[CLIENT] Sending turn: '{t}'", flush=True)
                await session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=t)]),
                    turn_complete=True
                )
                await asyncio.sleep(8.0)

        async def recv_worker():
            turn_count = 0
            async for response in session.receive():
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        print(f"  [RECV TOOL] {fc.name}", flush=True)
                        res = await execute_jarvis_tool(fc.name, fc.args)
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                        )
                if response.server_content:
                    if response.server_content.model_turn:
                        for p in response.server_content.model_turn.parts:
                            if p.text:
                                print(f"  [RECV TEXT] {p.text[:60]}...", flush=True)
                    if response.server_content.turn_complete:
                        turn_count += 1
                        print(f"  [RECV TURN COMPLETE #{turn_count}]", flush=True)
                        if turn_count >= 3:
                            break

        await asyncio.gather(send_worker(), recv_worker())
        print("\n[SUCCESS: 3 CONSECUTIVE TURNS COMPLETED!]")

if __name__ == "__main__":
    asyncio.run(test_live_session_turns())
