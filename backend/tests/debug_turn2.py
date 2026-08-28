import asyncio
import os
import sys
import traceback
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

async def test_debug_turn2():
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
        print("[CONNECTED]")

        # Turn 1
        print("\n--- SENDING TURN 1 ---", flush=True)
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="What is the live weather in Delhi?")]),
            turn_complete=True
        )

        async for response in session.receive():
            if response.tool_call:
                for fc in response.tool_call.function_calls:
                    print(f"  [T1 TOOL] {fc.name}", flush=True)
                    res = await execute_jarvis_tool(fc.name, fc.args)
                    print(f"  [T1 SENDING TOOL RES] {res.get('status')}", flush=True)
                    await session.send_tool_response(
                        function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                    )
            if response.server_content:
                if response.server_content.model_turn:
                    for p in response.server_content.model_turn.parts:
                        if p.inline_data:
                            print(f"  [T1 AUDIO] {len(p.inline_data.data)}", flush=True)
                if response.server_content.turn_complete:
                    print("  [T1 TURN COMPLETE]", flush=True)
                    break

        print("\n[T1 FULLY COMPLETED] Waiting 2 seconds before Turn 2...", flush=True)
        await asyncio.sleep(2.0)

        # Turn 2
        print("\n--- SENDING TURN 2 ---", flush=True)
        try:
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="What is the 72 hour air quality forecast?")]),
                turn_complete=True
            )
            print("  [T2 SEND SUCCESS]", flush=True)
        except Exception as e:
            print("  [T2 SEND EXCEPTION]:", e)
            traceback.print_exc()

        try:
            async for response in session.receive():
                if response.tool_call:
                    for fc in response.tool_call.function_calls:
                        print(f"  [T2 TOOL] {fc.name}", flush=True)
                        res = await execute_jarvis_tool(fc.name, fc.args)
                        print(f"  [T2 SENDING TOOL RES] {res.get('status')}", flush=True)
                        await session.send_tool_response(
                            function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                        )
                if response.server_content:
                    if response.server_content.model_turn:
                        for p in response.server_content.model_turn.parts:
                            if p.inline_data:
                                print(f"  [T2 AUDIO] {len(p.inline_data.data)}", flush=True)
                    if response.server_content.turn_complete:
                        print("  [T2 TURN COMPLETE]", flush=True)
                        break
        except Exception as e:
            print("  [T2 RECV EXCEPTION]:", e)
            traceback.print_exc()

        print("\n[END OF TEST]")

if __name__ == "__main__":
    asyncio.run(test_debug_turn2())
