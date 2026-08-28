import asyncio
import json
import os
import sys
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv()
if "GEMINI_API_KEY" in os.environ and os.environ.get("GEMINI_API_KEY"):
    os.environ["GOOGLE_API_KEY"] = os.environ["GEMINI_API_KEY"]
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

async def inspect_parts():
    client = genai.Client(http_options={'api_version': 'v1alpha'})
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(parts=[types.Part(text="You are VayuVani voice AI for Delhi NCR air quality. Never speak thought processes or markdown. Answer directly with tool data in 1 sentence.")]),
        tools=[{"function_declarations": JARVIS_TOOL_DECLARATIONS}]
    )
    async with client.aio.live.connect(model="gemini-2.5-flash-native-audio-latest", config=config) as session:
        print("[CONNECTED]")
        await session.send_client_content(
            turns=types.Content(role="user", parts=[types.Part(text="What is the live AQI at Anand Vihar station?")]),
            turn_complete=True
        )

        async for response in session.receive():
            sc = response.server_content
            if sc:
                if sc.model_turn:
                    for i, p in enumerate(sc.model_turn.parts):
                        print(f"PART {i}: text={repr(p.text)[:100]}, thought={getattr(p, 'thought', None)}, inline_data_len={len(p.inline_data.data) if p.inline_data else 0}")
                if sc.turn_complete:
                    print("TURN COMPLETE")
                    break

            if response.tool_call:
                for fc in response.tool_call.function_calls:
                    print(f"TOOL CALL: {fc.name} args={fc.args}")
                    res = await execute_jarvis_tool(fc.name, fc.args)
                    print(f"TOOL RESULT: {res}")
                    await session.send_tool_response(
                        function_responses=[types.FunctionResponse(
                            name=fc.name,
                            id=fc.id,
                            response={"result": res}
                        )]
                    )

if __name__ == "__main__":
    asyncio.run(inspect_parts())
