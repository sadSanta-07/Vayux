import os
import re
import logging
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

logger = logging.getLogger("VayuX.ModelSelector")

_CACHED_BEST_MODEL: Optional[str] = None
_CACHED_MODEL_INFO: Optional[Dict[str, Any]] = None

def _score_model_for_intelligence(name: str) -> int:
    """
    Dynamically score models to prioritize pure intelligence/reasoning capabilities.
    Calibrated against Artificial Analysis Intelligence Index hierarchies.
    """
    n = name.lower()
    score = 0

    # 1. Base Version Multiplier (The strongest indicator of intelligence)
    # E.g., 3.7 adds 3,700,000; 3.6 adds 3,600,000; 3.1 adds 3,100,000; 2.5 adds 2,500,000.
    m = re.search(r'(\d+)\.(\d+)', n)
    if m:
        major = int(m.group(1))
        minor = int(m.group(2))
        score += (major * 1000000) + (minor * 100000)
    else:
        m2 = re.search(r'gemini-(\d+)', n)
        if m2:
            major = int(m2.group(1))
            score += (major * 1000000)

    # 2. Base Tier Capabilities: Pro > Flash > Flash-Lite
    if "pro" in n:
        score += 300000
    elif "flash-lite" in n:
        score += 0
    elif "flash" in n:
        score += 100000

    # 3. Reasoning / Thinking Modifiers
    if any(kw in n for kw in ["thinking", "reasoning", "deep-think", "high"]):
        score += 90000
    elif "low" in n:
        score -= 150000

    # 4. Model State / Stability
    if "exp" in n or "experimental" in n:
        score += 0
    elif "preview" in n:
        score += 20
    else:
        score += 50

    # 5. Date Tie-Breaker
    date_match = re.search(r'-(\d{4,8})', n)
    if date_match:
        val = int(date_match.group(1))
        score += (val % 20)

    return score

def select_best_reasoning_model(api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Scans all available Gemini models in the account and dynamically selects
    the highest-intelligence text reasoning model for deep background delegation.
    """
    global _CACHED_BEST_MODEL, _CACHED_MODEL_INFO
    if _CACHED_MODEL_INFO is not None:
        return _CACHED_MODEL_INFO

    key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        fallback = {
            "model_id": "gemini-3.7-flash",
            "score": 3800050,
            "tier": "Generation 3.7 Ultra-Fast Thinking",
            "all_ranked_models": [{"model_id": "gemini-3.7-flash", "score": 3800050}]
        }
        _CACHED_BEST_MODEL = fallback["model_id"]
        _CACHED_MODEL_INFO = fallback
        return fallback

    try:
        client = genai.Client(api_key=key)
        all_models = client.models.list()
        
        # Filter out media-only models (veo, imagen, tts-only, transcription-only)
        excluded_keywords = ["veo", "imagen", "tts", "transcribe", "image-preview", "image"]
        
        candidates = []
        for m in all_models:
            model_id = m.name.replace("models/", "")
            lowered = model_id.lower()
            if any(kw in lowered for kw in excluded_keywords):
                continue
            if not ("gemini" in lowered):
                continue
            score = _score_model_for_intelligence(model_id)
            candidates.append({"model_id": model_id, "score": score, "display_name": getattr(m, "display_name", model_id)})

        # Sort descending by intelligence score
        candidates.sort(key=lambda x: x["score"], reverse=True)

        if not candidates:
            best_id = "gemini-3.7-flash"
            best_score = 3800050
        else:
            best_id = candidates[0]["model_id"]
            best_score = candidates[0]["score"]

        result = {
            "model_id": best_id,
            "score": best_score,
            "tier": f"Autonomous SOTA Reasoning ({best_id})",
            "all_ranked_models": candidates[:8]
        }
        _CACHED_BEST_MODEL = best_id
        _CACHED_MODEL_INFO = result
        logger.info(f"[ModelSelector] Selected best reasoning model: {best_id} (Score: {best_score})")
        return result
    except Exception as e:
        logger.warning(f"[ModelSelector] Failed to scan models: {e}. Defaulting to gemini-3.7-flash.")
        fallback = {
            "model_id": "gemini-3.7-flash",
            "score": 3800050,
            "tier": "Fallback SOTA Reasoning",
            "error": str(e)
        }
        _CACHED_BEST_MODEL = fallback["model_id"]
        _CACHED_MODEL_INFO = fallback
        return fallback

async def delegate_background_task(
    prompt: str,
    system_instruction: Optional[str] = None
) -> str:
    """
    GPT-Live Architecture: Delegates heavy, complex cognitive tasks
    (e.g., deep policy advisory, causal attribution, long-form synthesis)
    to the dynamically selected best text reasoning model with automatic candidate fallback.
    """
    model_info = select_best_reasoning_model()
    ranked = [m["model_id"] for m in model_info.get("all_ranked_models", [])]
    if not ranked:
        ranked = [model_info.get("model_id", "gemini-3.7-flash"), "gemini-3.6-flash", "gemini-2.5-pro", "gemini-2.5-flash"]

    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not key:
        return "[ModelSelector Error] No API key available for background delegation."

    client = genai.Client(api_key=key)
    
    config = types.GenerateContentConfig(
        temperature=0.2,
        system_instruction=system_instruction
    )
    
    for candidate in ranked[:4]:
        try:
            response = await client.aio.models.generate_content(
                model=candidate,
                contents=prompt,
                config=config
            )
            if response.text:
                return response.text
        except Exception as e:
            logger.warning(f"[ModelSelector] Attempt on {candidate} failed: {e}. Trying next candidate...")

    return "[Delegation Error] All reasoning candidate models failed to generate content."
