# app/gateways/pii.py
"""PII Gateway - Regex-based scrubbing for DPDP Act compliance."""
import re
from typing import List, Tuple
from app.config import get_settings

settings = get_settings()


class PIIGateway:
    """Redacts PII from text before LLM calls or logging."""

    def __init__(self):
        self.patterns = [
            (re.compile(settings.PII_PAN_REGEX), "[REDACTED_PAN]"),
            (re.compile(settings.PII_BANK_REGEX), "[REDACTED_BANK_ACCOUNT]"),
            (re.compile(settings.PII_AADHAAR_REGEX), "[REDACTED_AADHAAR]"),
        ]

    def redact(self, text: str) -> str:
        """Redact all PII patterns in text."""
        if not settings.PII_REDACTION_ENABLED:
            return text
        for pattern, replacement in self.patterns:
            text = pattern.sub(replacement, text)
        return text

    def redact_dict(self, data: dict) -> dict:
        """Recursively redact PII in dictionary values."""
        if isinstance(data, dict):
            return {k: self.redact_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.redact_dict(v) for v in data]
        elif isinstance(data, str):
            return self.redact(data)
        return data

    def find_pii(self, text: str) -> List[Tuple[str, str, int, int]]:
        """Find all PII matches with positions."""
        matches = []
        for pattern, label in [(p, r) for p, r in self.patterns]:
            for match in pattern.finditer(text):
                matches.append((label, match.group(), match.start(), match.end()))
        return matches


# Singleton instance
pii_gateway = PIIGateway()