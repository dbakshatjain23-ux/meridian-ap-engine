# app/gateways/llm.py
"""LLM Gateway - Anthropic Claude Only (Haiku + Sonnet Tiering)."""
import hashlib
import json
import time
from typing import Optional
from dataclasses import dataclass
from anthropic import AsyncAnthropic
from app.config import get_settings

settings = get_settings()


@dataclass
class LLMResponse:
    content: str
    model: str
    usage: dict
    cached: bool = False


class LRUCache:
    """Simple LRU cache for LLM responses."""

    def __init__(self, maxsize: int = 10000):
        self.maxsize = maxsize
        self.cache: dict = {}
        self.access_order: list = []

    def _make_key(self, model: str, prompt: str, system: Optional[str], temperature: float) -> str:
        data = f"{model}|{system or ''}|{temperature}|{prompt}"
        return hashlib.sha256(data.encode()).hexdigest()

    def get(self, key: str) -> Optional[LLMResponse]:
        if key in self.cache:
            # Move to end (most recently used)
            self.access_order.remove(key)
            self.access_order.append(key)
            return self.cache[key]
        return None

    def set(self, key: str, value: LLMResponse) -> None:
        if key in self.cache:
            self.access_order.remove(key)
        elif len(self.cache) >= self.maxsize:
            # Evict least recently used
            oldest = self.access_order.pop(0)
            del self.cache[oldest]
        self.cache[key] = value
        self.access_order.append(key)


class PIIRedactor:
    """Redacts PII before sending to LLM."""

    def __init__(self):
        import re
        self.pan_pattern = re.compile(settings.PII_PAN_REGEX)
        self.bank_pattern = re.compile(settings.PII_BANK_REGEX)
        self.aadhaar_pattern = re.compile(settings.PII_AADHAAR_REGEX)

    def redact(self, text: str) -> str:
        if not settings.PII_REDACTION_ENABLED:
            return text
        text = self.pan_pattern.sub("[REDACTED_PAN]", text)
        text = self.bank_pattern.sub("[REDACTED_BANK_ACCOUNT]", text)
        text = self.aadhaar_pattern.sub("[REDACTED_AADHAAR]", text)
        return text


class CallLogger:
    """Logs all LLM calls for observability."""

    def __init__(self):
        self.calls = []

    def log(self, task_type: str, prompt: str, response: str, model: str, cached: bool, latency_ms: int) -> None:
        self.calls.append({
            "timestamp": time.time(),
            "task_type": task_type,
            "model": model,
            "prompt_tokens": len(prompt) // 4,  # rough estimate
            "response_tokens": len(response) // 4,
            "cached": cached,
            "latency_ms": latency_ms,
        })


class LLMGateway:
    """
    Single gateway for all Anthropic Claude calls.
    Two-model tiering: Haiku for cheap/fast, Sonnet for strong reasoning.
    """

    HAIKU_TASKS = {
        "triage", "routing", "structure_repair", "schema_learning",
        "classification", "simple_extraction", "entity_extraction",
    }

    def __init__(self):
        self.haiku = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.sonnet = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.pii_redactor = PIIRedactor()
        self.call_logger = CallLogger()
        self.cache = LRUCache()

    def _route_model(self, task_type: str) -> tuple[AsyncAnthropic, str]:
        """Route to appropriate model tier."""
        if task_type in self.HAIKU_TASKS:
            return self.haiku, settings.CLAUDE_HAIKU_MODEL
        return self.sonnet, settings.CLAUDE_SONNET_MODEL

    async def complete(
        self,
        task_type: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> str:
        """
        Complete a prompt with automatic PII redaction, caching, and logging.
        """
        start_time = time.time()

        # 1. Redact PII from prompt
        clean_prompt = self.pii_redactor.redact(prompt)
        clean_system = self.pii_redactor.redact(system) if system else None

        # 2. Check cache
        cache_key = self.cache._make_key(
            task_type, clean_prompt, clean_system, temperature
        )
        if cached := self.cache.get(cache_key):
            self.call_logger.log(task_type, clean_prompt, cached.content, cached.model, True, int((time.time() - start_time) * 1000))
            return cached.content

        # 3. Route to model
        client, model = self._route_model(task_type)

        # 4. Call with retries
        last_error = None
        for attempt in range(settings.LLM_MAX_RETRIES):
            try:
                response = await client.messages.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=clean_system,
                    messages=[{"role": "user", "content": clean_prompt}],
                )
                content = response.content[0].text if response.content else ""
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                break
            except Exception as e:
                last_error = e
                if attempt < settings.LLM_MAX_RETRIES - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise

        latency_ms = int((time.time() - start_time) * 1000)

        # 5. Cache and log
        llm_response = LLMResponse(content=content, model=model, usage=usage)
        self.cache.set(cache_key, llm_response)
        self.call_logger.log(task_type, clean_prompt, content, model, False, latency_ms)

        return content

    async def complete_json(
        self,
        task_type: str,
        prompt: str,
        system: Optional[str] = None,
        schema: Optional[dict] = None,
    ) -> dict:
        """Complete and parse JSON response with schema validation."""
        import json
        # Add JSON instruction to system prompt
        json_system = (system or "") + "\n\nYou must respond with valid JSON only. No markdown, no explanation."
        if schema:
            json_system += f"\nSchema: {json.dumps(schema)}"

        response = await self.complete(task_type, prompt, json_system, temperature=0.0)
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from response
            import re
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            raise ValueError(f"Failed to parse JSON from LLM response: {response[:200]}")


# Singleton instance
llm_gateway = LLMGateway()


import asyncio