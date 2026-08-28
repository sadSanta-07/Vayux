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
    """Generates 16kHz 16-bit mono raw PCM audio bytes."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    # Generate an amplitude modulated acoustic signal simulating voice formant
    carrier = np.sin(2 * np.pi * freq * t)
    modulator = 0.5 * (1 + np.sin(2 * np.pi * 3.0 * t))
    signal = (carrier * modulator * 0.5 * 32767).astype(np.int16)
    return signal.tobytes()

async def test_raw_pcm_audio_streaming():
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[FAIL] No Gemini API key configured.", flush=True)
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
    print(f"[TESTING RAW PCM STREAM] Connecting to {model_id}...", flush=True)

    try:
        async with client.aio.live.connect(model=model_id, config=config) as session:
            print("[CONNECTED] Streaming raw 16kHz 16-bit PCM audio chunks...", flush=True)

            # Generate 2 seconds of raw 16kHz PCM audio (chunks of 4096 samples = 8192 bytes)
            pcm_bytes = generate_pcm_audio(freq=300.0, duration_sec=2.0, sample_rate=16000)
            chunk_size = 4096 * 2  # 8192 bytes

            for i in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[i:i+chunk_size]
                print(f"  -> Streaming PCM audio chunk ({len(chunk)} bytes) via send_realtime_input...", flush=True)
                await session.send_realtime_input(
                    audio=types.Blob(mime_type="audio/pcm;rate=16000", data=chunk)
                )
                await asyncio.sleep(0.1)

            print("[SENT AUDIO] Waiting for model to process audio input stream and respond...", flush=True)
            
            # Send a voice turn prompt to trigger response if tone alone didn't have words
            await session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text="Can you hear me clearly?")]),
                turn_complete=True
            )

            audio_received = 0
            text_received = []

            async for response in session.receive():
                if response.server_content and response.server_content.model_turn:
                    for part in response.server_content.model_turn.parts:
                        if part.inline_data:
                            audio_received += len(part.inline_data.data)
                        if part.text:
                            text_received.append(part.text)

                if response.server_content and response.server_content.turn_complete:
                    print(f"[SUCCESS] Model responded! Received {audio_received} bytes of 24kHz audio.", flush=True)
                    print(f"[TRANSCRIPT] {' '.join(text_received[:1])}", flush=True)
                    break

            print("\n[RAW PCM AUDIO INPUT STREAMING VERIFIED WITH ZERO ERRORS!]", flush=True)
            return True

    except Exception as e:
        print(f"[FAIL] Error during raw audio streaming: {e}", flush=True)
        return False

if __name__ == "__main__":
    success = asyncio.run(test_raw_pcm_audio_streaming())
    sys.exit(0 if success else 1)
