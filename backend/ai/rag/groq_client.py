import os
import logging
from typing import List, Optional
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
logger = logging.getLogger(__name__)

def get_groq_api_keys() -> List[str]:
    """
    Load Groq API keys from environment variables.
    Supports comma-separated GROQ_API_KEYS or individual variables:
    GROQ_API_KEY, GROQ_API_KEY_1, GROQ_API_KEY_2, GROQ_API_KEY_3, GROQ_API_KEY_ROTATION.
    """
    keys = []

    # 1. Comma-separated GROQ_API_KEYS
    raw_keys = os.getenv("GROQ_API_KEYS")
    if raw_keys:
        for k in raw_keys.split(","):
            k_clean = k.strip()
            if k_clean and k_clean not in keys:
                keys.append(k_clean)

    # 2. Individual keys
    for var_name in ["GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2", "GROQ_API_KEY_3", "GROQ_API_KEY_ROTATION"]:
        val = os.getenv(var_name)
        if val:
            val_clean = val.strip()
            if val_clean and val_clean not in keys:
                keys.append(val_clean)

    return keys

def is_rate_limit_or_quota_error(error: Exception) -> bool:
    """
    Detect if the exception is a 429 Rate Limit, Token Limit, or Quota Exceeded error.
    """
    err_str = str(error).lower()
    if "429" in err_str or "rate limit" in err_str or "tokens per day" in err_str or "tpd" in err_str or "quota" in err_str:
        return True
    return False

def is_model_not_found_error(error: Exception) -> bool:
    err_str = str(error).lower()
    return "404" in err_str or "model_not_found" in err_str or "model not found" in err_str

def is_invalid_api_key_error(error: Exception) -> bool:
    err_str = str(error).lower()
    return "401" in err_str or "invalid api key" in err_str or "authentication" in err_str

def ask_llm(prompt: str, system_prompt: Optional[str] = None, model: str = "openai/gpt-oss-20b") -> Optional[str]:
    """
    Query Groq LLM with API Key Rotation and Rate-Limit (429) Handling.
    Rotates to the next available API key if 429 Rate Limit occurs.
    If all keys fail or hit rate limits, returns None gracefully (triggering local RAG fallback).
    """
    api_keys = get_groq_api_keys()
    if not api_keys:
        logger.warning("[GROQ] No GROQ_API_KEY found in .env. Falling back to local RAG generator.")
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for idx, key in enumerate(api_keys):
        try:
            logger.info(f"[GROQ] Querying Groq API using Key #{idx + 1} (ending in ...{key[-4:] if len(key) >= 4 else '***'})...")
            client = Groq(api_key=key)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
            )
            if response and response.choices and len(response.choices) > 0:
                content = response.choices[0].message.content
                if content and content.strip():
                    return content.strip()
            logger.warning(f"[GROQ] Empty choice response received from Key #{idx + 1}.")
        except Exception as e:
            if is_model_not_found_error(e):
                logger.error(f"[GROQ_404_MODEL_NOT_FOUND] Model '{model}' not found: {e}")
                return None
            elif is_invalid_api_key_error(e):
                logger.error(f"[GROQ_401_INVALID_KEY] Key #{idx + 1} is invalid: {e}")
                continue
            elif is_rate_limit_or_quota_error(e):
                logger.warning(f"[GROQ_RATE_LIMIT_429] Key #{idx + 1} hit 429 Rate Limit: {e}. Rotating to next API key in pool...")
                continue
            else:
                logger.error(f"[GROQ_ERROR] Error querying Groq API with Key #{idx + 1}: {e}")
                continue

    logger.warning("[GROQ_ALL_KEYS_EXHAUSTED] All Groq API keys were exhausted or hit 429 rate limits. Using intelligent local fallback generator.")
    return None