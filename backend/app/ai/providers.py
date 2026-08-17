"""AI Integrations gateway.

Bring-Your-Own-Key: users register their own API keys (encrypted at rest with
AES-256). The gateway speaks each provider's native API:

  OpenAI / Groq / DeepSeek / Mistral / OpenRouter / OpenAI-compatible / Azure
  Anthropic (Claude)   — /v1/messages
  Google Gemini        — /v1beta/models/{model}:generateContent
  Ollama               — local /api/chat

Keys are never returned by the API; only masked previews are exposed. Test
connection performs a minimal authenticated request against each provider.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import httpx

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


@dataclass
class ProviderSpec:
    provider_type: str
    label: str
    default_base_url: str
    default_models: List[str]
    requires_key: bool = True


PROVIDER_SPECS: List[ProviderSpec] = [
    ProviderSpec("openai", "OpenAI", "https://api.openai.com/v1", ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]),
    ProviderSpec("anthropic", "Anthropic (Claude)", "https://api.anthropic.com", ["claude-3-5-sonnet-20241022", "claude-3-5-haiku-20241022"]),
    ProviderSpec("gemini", "Google Gemini", "https://generativelanguage.googleapis.com", ["gemini-1.5-pro", "gemini-1.5-flash"]),
    ProviderSpec("groq", "Groq", "https://api.groq.com/openai/v1", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]),
    ProviderSpec("deepseek", "DeepSeek", "https://api.deepseek.com/v1", ["deepseek-chat", "deepseek-reasoner"]),
    ProviderSpec("openrouter", "OpenRouter", "https://openrouter.ai/api/v1", ["openrouter/auto", "meta-llama/llama-3.3-70b-instruct"]),
    ProviderSpec("mistral", "Mistral", "https://api.mistral.ai/v1", ["mistral-large-latest", "mistral-small-latest"]),
    ProviderSpec("ollama", "Ollama (local)", "http://localhost:11434", ["llama3.1", "qwen2.5:7b"], requires_key=False),
    ProviderSpec("azure_openai", "Azure OpenAI", "https://YOUR_RESOURCE.openai.azure.com", ["gpt-4o", "gpt-35-turbo"]),
    ProviderSpec("openai_compatible", "OpenAI Compatible", "https://api.example.com/v1", ["default"]),
]

SPEC_MAP: Dict[str, ProviderSpec] = {s.provider_type: s for s in PROVIDER_SPECS}


def provider_specs_public() -> List[dict]:
    return [
        {
            "provider_type": s.provider_type,
            "label": s.label,
            "default_base_url": s.default_base_url,
            "default_models": s.default_models,
            "requires_key": s.requires_key,
        }
        for s in PROVIDER_SPECS
    ]


def _chat_openai(base_url: str, key: str, model: str, messages: List[dict], temperature: float) -> dict:
    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    body = {"model": model, "messages": messages, "temperature": temperature}
    resp = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    usage = data.get("usage", {})
    return {"content": content, "tokens": usage.get("total_tokens", 0), "raw": data}


def _chat_anthropic(base_url: str, key: str, model: str, messages: List[dict], temperature: float) -> dict:
    url = f"{base_url.rstrip('/')}/v1/messages"
    headers = {"x-api-key": key, "anthropic-version": "2023-06-01", "Content-Type": "application/json"}
    system = "\n".join(m["content"] for m in messages if m["role"] == "system")
    user_msgs = [m for m in messages if m["role"] != "system"]
    body = {
        "model": model,
        "max_tokens": 1024,
        "temperature": temperature,
        "messages": user_msgs,
    }
    if system:
        body["system"] = system
    resp = httpx.post(url, json=body, headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    content = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    usage = data.get("usage", {})
    return {"content": content, "tokens": usage.get("input_tokens", 0) + usage.get("output_tokens", 0), "raw": data}


def _chat_gemini(base_url: str, key: str, model: str, messages: List[dict], temperature: float) -> dict:
    url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent"
    parts = []
    for m in messages:
        if m["role"] == "system":
            parts.append({"text": m["content"]})
    for m in messages:
        if m["role"] == "user":
            parts.append({"text": m["content"]})
        elif m["role"] == "assistant":
            parts.append({"text": m["content"]})
    body = {"contents": [{"parts": parts}], "generationConfig": {"temperature": temperature}}
    resp = httpx.post(url, params={"key": key}, json=body, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates", [])
    content = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", [])) if candidates else ""
    usage = data.get("usageMetadata", {})
    return {"content": content, "tokens": usage.get("totalTokenCount", 0), "raw": data}


def _chat_ollama(base_url: str, key: str, model: str, messages: List[dict], temperature: float) -> dict:
    url = f"{base_url.rstrip('/')}/api/chat"
    body = {"model": model, "messages": messages, "stream": False, "options": {"temperature": temperature}}
    resp = httpx.post(url, json=body, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    return {"content": data.get("message", {}).get("content", ""), "tokens": 0, "raw": data}


def chat_completion(
    provider_type: str,
    base_url: str,
    api_key: str,
    model: str,
    messages: List[dict],
    temperature: float = 0.3,
    timeout: float = 60.0,
) -> dict:
    """Route a chat request to the provider's native API."""
    global TIMEOUT
    TIMEOUT = httpx.Timeout(timeout, connect=10.0)
    if provider_type in ("openai", "groq", "deepseek", "openrouter", "mistral", "azure_openai", "openai_compatible"):
        return _chat_openai(base_url, api_key, model, messages, temperature)
    if provider_type == "anthropic":
        return _chat_anthropic(base_url, api_key, model, messages, temperature)
    if provider_type == "gemini":
        return _chat_gemini(base_url, api_key, model, messages, temperature)
    if provider_type == "ollama":
        return _chat_ollama(base_url, api_key, model, messages, temperature)
    raise ValueError(f"Unsupported provider type: {provider_type}")


def test_provider(provider_type: str, base_url: str, api_key: str, model: str = "") -> dict:
    """Minimal authenticated request to verify credentials."""
    start_import = __import__("time").time()
    try:
        if provider_type in ("openai", "groq", "deepseek", "openrouter", "mistral", "azure_openai", "openai_compatible"):
            model = model or SPEC_MAP.get(provider_type, ProviderSpec("", "", "", [])).default_models[0]
            result = _chat_openai(base_url, api_key, model, [{"role": "user", "content": "ping"}], 0.0)
        elif provider_type == "anthropic":
            model = model or "claude-3-5-haiku-20241022"
            result = _chat_anthropic(base_url, api_key, model, [{"role": "user", "content": "ping"}], 0.0)
        elif provider_type == "gemini":
            model = model or "gemini-1.5-flash"
            result = _chat_gemini(base_url, api_key, model, [{"role": "user", "content": "ping"}], 0.0)
        elif provider_type == "ollama":
            result = _chat_ollama(base_url, "", model or "llama3.1", [{"role": "user", "content": "ping"}], 0.0)
        else:
            raise ValueError("unsupported")
        latency = int((__import__("time").time() - start_import) * 1000)
        return {"ok": True, "latency_ms": latency, "message": f"Connected ({latency} ms)"}
    except httpx.HTTPStatusError as e:
        return {"ok": False, "latency_ms": 0, "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "latency_ms": 0, "message": str(e)[:300]}
