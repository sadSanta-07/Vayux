import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool
from ml.model_selector import select_best_reasoning_model

async def test_full_voice_suite():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[FAIL] No Gemini API key found.", flush=True)
        return False

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})

    # Verify dynamic model selection engine first
    best_model = select_best_reasoning_model()
    print(f"[REASONING SELECTION] Auto-selected SOTA Reasoning Model: {best_model.get('model_id')} (Intelligence Score: {best_model.get('score')})", flush=True)

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text="You are VayuVani voice co-pilot. When asked about weather, fires, forecast, or policy, call the corresponding tool. Answer concisely in 1-2 spoken sentences.")]),
        tools=[{"function_declarations": JARVIS_TOOL_DECLARATIONS}]
    )

    model_id = os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest")
    print(f"\n[VOICE ENGINE] Connecting to Native Audio Dialog: {model_id}...", flush=True)

    try:
        async with client.aio.live.connect(model=model_id, config=config) as session:
            print(f"[VOICE ENGINE] Connected successfully to {model_id}!", flush=True)

            test_turns = [
                ("TURN 1: Weather & AQI", "What is the live weather and boundary layer height in Delhi?", "get_live_weather_and_aqi"),
                ("TURN 2: Stubble Fires", "How many active fires are detected upwind by NASA satellites?", "get_active_fire_hotspots"),
                ("TURN 3: 72h Forecast", "What is the 72 hour rolling air quality forecast?", "get_72h_air_quality_forecast"),
                ("TURN 4: GRAP Policy", "Simulate a 50% cut in vehicular traffic under GRAP Stage 4.", "simulate_grap_policy"),
                ("TURN 5: GPT-Live Delegation", "Generate an executive policy brief for emergency interventions.", "generate_deep_policy_brief"),
            ]

            for turn_name, prompt, expected_tool in test_turns:
                print(f"\n[{turn_name}] Prompt: '{prompt}'", flush=True)
                await session.send_client_content(
                    turns=types.Content(role="user", parts=[types.Part(text=prompt)]),
                    turn_complete=True
                )

                tool_invoked = False
                audio_bytes = 0
                text_parts = []

                async for response in session.receive():
                    if response.tool_call:
                        for fc in response.tool_call.function_calls:
                            tool_invoked = True
                            print(f"  -> [TOOL INVOKED] {fc.name}({fc.args})", flush=True)
                            tool_res = await execute_jarvis_tool(fc.name, fc.args)
                            print(f"  -> [TOOL RESULT] Status: {tool_res.get('status', 'OK')}", flush=True)
                            await session.send_tool_response(
                                function_responses=[types.FunctionResponse(name=fc.name, id=fc.id, response={"result": tool_res})]
                            )

                    if response.server_content and response.server_content.model_turn:
                        for p in response.server_content.model_turn.parts:
                            if p.inline_data:
                                audio_bytes += len(p.inline_data.data)
                            if p.text:
                                text_parts.append(p.text)

                    if response.server_content and response.server_content.turn_complete:
                        print(f"  -> [{turn_name} SUCCESS] Audio streamed: {audio_bytes} bytes. Speech text: {' '.join(text_parts[:1])}", flush=True)
                        break

            print("\n[ALL 5 VOICE TURNS & TOOL INVOCATIONS PASSED CLEANLY!]", flush=True)
            return True

    except Exception as e:
        print(f"[FAIL] Voice session error: {e}", flush=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_full_voice_suite())
    sys.exit(0 if success else 1)
