import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

async def test_multiturn():
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

        # Queue to pass incoming responses
        async def response_reader():
            try:
                async for response in session.receive():
                    if response.tool_call:
                        for fc in response.tool_call.function_calls:
                            print(f"  -> [TOOL CALL] {fc.name}({fc.args})", flush=True)
                            res = await execute_jarvis_tool(fc.name, fc.args)
                            print(f"  -> [TOOL RES] {res.get('status')}", flush=True)
                            await session.send_tool_response(
                                function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": res})]
                            )
                    if response.server_content:
                        if response.server_content.model_turn:
                            for p in response.server_content.model_turn.parts:
                                if p.inline_data:
                                    print(f"  -> [AUDIO] {len(p.inline_data.data)} bytes", flush=True)
                        if response.server_content.turn_complete:
                            print("  -> [TURN COMPLETE]", flush=True)
            except Exception as e:
                print(f"Reader error: {e}", flush=True)

        reader_task = asyncio.create_task(response_reader())

        # Turn 1
        print("\n--- SENDING TURN 1 ---", flush=True)
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="What is the live weather in Delhi?")]),
            turn_complete=True
        )
        await asyncio.sleep(6.0)

        # Turn 2
        print("\n--- SENDING TURN 2 ---", flush=True)
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="How many stubble fires are upwind?")]),
            turn_complete=True
        )
        await asyncio.sleep(6.0)

        # Turn 3
        print("\n--- SENDING TURN 3 ---", flush=True)
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="What is the 72 hour AQI forecast?")]),
            turn_complete=True
        )
        await asyncio.sleep(6.0)

        reader_task.cancel()
        print("\n[TEST FINISHED]")

if __name__ == "__main__":
    asyncio.run(test_multiturn())
