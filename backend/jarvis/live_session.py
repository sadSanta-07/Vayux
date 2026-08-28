import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from jarvis.tools import JARVIS_TOOL_DECLARATIONS, execute_jarvis_tool

logger = logging.getLogger("VayuX.VayuVaniLive")

VAYUVANI_SYSTEM_INSTRUCTION = """
You are "VayuVani" (वायुवाणी), the real-time conversational voice AI co-pilot for the VayuX atmospheric intelligence platform in Delhi NCR.

CRITICAL VOICE RULES:
1. NEVER speak internal thought processes, planning commentary, tool analysis, or markdown headers (e.g. NEVER say "**Assessing Query**" or "I am searching"). Speak ONLY direct, friendly, natural spoken answers.
2. Multilingual: Respond in the exact language the user speaks (English, Hindi, or Hinglish).
3. Spoken replies must be crisp, accurate, and conversational (1-2 sentences maximum).
4. Direct Tool Invocation:
   - For ANY query about a SPECIFIC station, locality, or landmark (e.g. 'Anand Vihar', 'Punjabi Bagh', 'ITO', 'Dwarka', 'Rohini', 'Noida', 'Gurugram', 'Ghaziabad', 'Alipur'): IMMEDIATELY call `get_station_aqi_and_details` with `location_name`.
   - For ANY query about forecasted temperature, upcoming weather, or 72-hour pollution trends: IMMEDIATELY call `get_72h_air_quality_forecast`.
   - For ANY query about regional weather, current temperature, humidity, wind, or overall NCR AQI: IMMEDIATELY call `get_live_weather_and_aqi`.
   - For ANY query requiring current web news, CAQM directives, Supreme Court rulings, school closures, or general environmental facts: IMMEDIATELY call `search_environmental_and_news_intel`.
   - For stubble burning / farm fires: IMMEDIATELY call `get_active_fire_hotspots`.
   - For Odd-Even or GRAP counterfactual simulations: IMMEDIATELY call `simulate_grap_policy`.
5. Once tool data arrives, speak the exact metrics directly and concisely.
"""

# Supported SOTA Native Audio Dialog Models in order of capability
VOICE_MODELS_FALLBACK = [
    os.getenv("GEMINI_LIVE_MODEL", "gemini-2.5-flash-native-audio-latest"),
    "gemini-2.5-flash-native-audio-preview-12-2025",
    "gemini-2.0-flash-exp"
]

async def handle_jarvis_live_websocket(websocket: WebSocket):
    """
    Bi-directional continuous WebSocket streaming audio between browser and Gemini Multimodal Live API.
    """
    await websocket.accept()
    logger.info("VayuVani Live Client Connected via WebSocket.")
    
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured on server."})
        await websocket.close()
        return

    client = genai.Client(api_key=api_key, http_options={'api_version': 'v1alpha'})

    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
            )
        ),
        system_instruction=types.Content(parts=[types.Part(text=VAYUVANI_SYSTEM_INSTRUCTION)]),
        tools=[{"function_declarations": JARVIS_TOOL_DECLARATIONS}]
    )

    session = None
    connected_model = None

    for candidate_model in VOICE_MODELS_FALLBACK:
        try:
            logger.info(f"Attempting connection to voice model: {candidate_model}")
            session_context = client.aio.live.connect(model=candidate_model, config=config)
            session = await session_context.__aenter__()
            connected_model = candidate_model
            logger.info(f"Connected to Gemini Live Multimodal Session on {candidate_model}")
            break
        except Exception as e:
            logger.warning(f"Voice model {candidate_model} unavailable: {e}")

    if session is None:
        await websocket.send_json({"type": "error", "message": "Could not connect to any Gemini Live audio model."})
        await websocket.close()
        return

    try:
        await websocket.send_json({
            "type": "status",
            "message": "connected",
            "assistant": "VayuVani",
            "voice_model": connected_model
        })

        async def receive_from_browser():
            try:
                while True:
                    data = await websocket.receive()
                    msg_type = data.get("type")
                    if msg_type == "websocket.disconnect":
                        logger.info("Browser client disconnected cleanly.")
                        break

                    if "bytes" in data and data["bytes"]:
                        # Forward 16kHz PCM audio chunk directly to Gemini Live
                        await session.send_realtime_input(
                            media=types.Blob(mime_type="audio/pcm;rate=16000", data=data["bytes"])
                        )
                    elif "text" in data and data["text"]:
                        msg = json.loads(data["text"])
                        logger.info(f"Received client message: {msg.get('type')}")
                        if msg.get("type") == "text_query":
                            query_text = msg.get("text", "")
                            if query_text:
                                logger.info(f"Forwarding text query to Gemini Live: '{query_text}'")
                                await session.send_client_content(
                                    turns=types.Content(role="user", parts=[types.Part(text=query_text)]),
                                    turn_complete=True
                                )
                                logger.info("Successfully sent text query to Gemini Live")
            except WebSocketDisconnect:
                logger.info("Browser disconnected from audio input stream.")
            except Exception as e:
                logger.error(f"Receive loop error: {e}", exc_info=True)

        async def send_to_browser():
            try:
                while True:
                    async for response in session.receive():
                        server_content = response.server_content
                        if server_content is not None:
                            if server_content.interrupted:
                                logger.info("VayuVani Turn Interrupted by User")
                                await websocket.send_json({"type": "interrupted"})

                            model_turn = server_content.model_turn
                            if model_turn is not None:
                                for part in model_turn.parts:
                                    # Filter out internal thoughts and planning text from the user transcript
                                    is_thought = getattr(part, 'thought', False)
                                    if part.text and not is_thought and not part.text.strip().startswith("**"):
                                        await websocket.send_json({"type": "transcript", "text": part.text})
                                    if part.inline_data:
                                        # Stream 24kHz audio bytes back to browser
                                        await websocket.send_bytes(part.inline_data.data)

                            if server_content.turn_complete:
                                logger.info("VayuVani Turn Complete")
                                await websocket.send_json({"type": "turn_complete"})

                        # Handle Tool Calls
                        tool_call = response.tool_call
                        if tool_call is not None:
                            for fc in tool_call.function_calls:
                                logger.info(f"VayuVani Tool Invocation: {fc.name}")
                                tool_result = await execute_jarvis_tool(fc.name, fc.args)
                                await session.send_tool_response(
                                    function_responses=[types.FunctionResponse(
                                        name=fc.name,
                                        id=fc.id,
                                        response={"result": tool_result}
                                    )]
                                )
            except WebSocketDisconnect:
                logger.info("Browser disconnected from audio output stream.")
            except Exception as e:
                logger.error(f"Send loop error: {e}", exc_info=True)

        import asyncio
        await asyncio.gather(receive_from_browser(), send_to_browser())

    except WebSocketDisconnect:
        logger.info("VayuVani Live Client Disconnected cleanly.")
    except Exception as e:
        logger.error(f"VayuVani Live Session Error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except:
            pass
    finally:
        try:
            await session_context.__aexit__(None, None, None)
        except:
            pass
