import asyncio
import os
import json
import logging
from dotenv import load_dotenv

load_dotenv()
from fastapi import WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types
from gemini_keys import get_gemini_api_key, is_rate_limit_error
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


class _BrowserDisconnected(Exception):
    pass


async def _connect_voice_session(api_key: str, config: types.LiveConnectConfig):
    for candidate_model in VOICE_MODELS_FALLBACK:
        try:
            logger.info("Attempting connection to voice model: %s", candidate_model)
            client = genai.Client(
                api_key=api_key,
                http_options={"api_version": "v1alpha"},
            )
            session_context = client.aio.live.connect(
                model=candidate_model,
                config=config,
            )
            session = await session_context.__aenter__()
            logger.info(
                "Connected to Gemini Live Multimodal Session on %s",
                candidate_model,
            )
            return session_context, session, candidate_model, None
        except Exception as error:
            if is_rate_limit_error(error):
                return None, None, None, "rate_limited"

            logger.warning(
                "Voice model %s unavailable with %s.",
                candidate_model,
                type(error).__name__,
            )

    return None, None, None, "models_unavailable"


async def _bridge_voice_session(websocket: WebSocket, session):
    async def receive_from_browser():
        while True:
            try:
                data = await websocket.receive()
            except WebSocketDisconnect as error:
                raise _BrowserDisconnected from error

            if data.get("type") == "websocket.disconnect":
                raise _BrowserDisconnected

            if data.get("bytes"):
                await session.send_realtime_input(
                    media=types.Blob(
                        mime_type="audio/pcm;rate=16000",
                        data=data["bytes"],
                    )
                )
            elif data.get("text"):
                message = json.loads(data["text"])
                logger.info("Received client message: %s", message.get("type"))
                if message.get("type") == "text_query":
                    query_text = message.get("text", "")
                    if query_text:
                        await session.send_client_content(
                            turns=types.Content(
                                role="user",
                                parts=[types.Part(text=query_text)],
                            ),
                            turn_complete=True,
                        )

    async def send_to_browser():
        try:
            # Gemini's receive iterator ends at the end of each model turn. Start a
            # fresh iterator for the next turn while keeping the Live session open.
            while True:
                received_response = False
                async for response in session.receive():
                    received_response = True
                    server_content = response.server_content
                    if server_content is not None:
                        if server_content.interrupted:
                            logger.info("VayuVani Turn Interrupted by User")
                            await websocket.send_json({"type": "interrupted"})

                        model_turn = server_content.model_turn
                        if model_turn is not None:
                            for part in model_turn.parts:
                                is_thought = getattr(part, "thought", False)
                                if (
                                    part.text
                                    and not is_thought
                                    and not part.text.strip().startswith("**")
                                ):
                                    await websocket.send_json(
                                        {"type": "transcript", "text": part.text}
                                    )
                                if part.inline_data:
                                    await websocket.send_bytes(part.inline_data.data)

                        if server_content.turn_complete:
                            logger.info("VayuVani Turn Complete")
                            await websocket.send_json({"type": "turn_complete"})

                    tool_call = response.tool_call
                    if tool_call is not None:
                        for function_call in tool_call.function_calls:
                            logger.info(
                                "VayuVani Tool Invocation: %s",
                                function_call.name,
                            )
                            tool_result = await execute_jarvis_tool(
                                function_call.name,
                                function_call.args,
                            )
                            await session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(
                                        name=function_call.name,
                                        id=function_call.id,
                                        response={"result": tool_result},
                                    )
                                ]
                            )

                if not received_response:
                    raise RuntimeError("Gemini Live connection closed without a response.")
        except WebSocketDisconnect as error:
            raise _BrowserDisconnected from error

    tasks = [
        asyncio.create_task(receive_from_browser()),
        asyncio.create_task(send_to_browser()),
    ]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def handle_jarvis_live_websocket(websocket: WebSocket):
    """
    Bi-directional continuous WebSocket streaming audio between browser and Gemini Multimodal Live API.
    """
    await websocket.accept()
    logger.info("VayuVani Live Client Connected via WebSocket.")
    
    api_key = get_gemini_api_key()
    if not api_key:
        await websocket.send_json({"type": "error", "message": "GEMINI_API_KEY is not configured on server."})
        await websocket.close()
        return

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

    session_context, session, connected_model, failure = await _connect_voice_session(
        api_key,
        config,
    )

    if session is None:
        message = (
            "The configured Gemini API key is rate limited. Try again later."
            if failure == "rate_limited"
            else "Could not connect to any Gemini Live audio model."
        )
        await websocket.send_json({"type": "error", "message": message})
        await websocket.close()
        return

    try:
        await websocket.send_json({
            "type": "status",
            "message": "connected",
            "assistant": "VayuVani",
            "voice_model": connected_model,
        })
        await _bridge_voice_session(websocket, session)
    except _BrowserDisconnected:
        logger.info("VayuVani Live Client Disconnected cleanly.")
    except Exception as error:
        rate_limited = is_rate_limit_error(error)
        logger.error(
            "VayuVani Live Session failed with %s.",
            type(error).__name__,
            exc_info=True,
        )
        try:
            await websocket.send_json({
                "type": "error",
                "message": (
                    "The configured Gemini API key is rate limited. Try again later."
                    if rate_limited
                    else "The VayuVani live session ended unexpectedly. Please try again."
                ),
            })
            await websocket.close()
        except Exception:
            pass
    finally:
        try:
            await session_context.__aexit__(None, None, None)
        except Exception:
            pass
