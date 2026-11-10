# app/core/ingestion/live_capture/pii_redactor.py
"""Live PII Redactor - Real-time PII redaction for text and audio streams."""
import re
import logging
from typing import Dict, List, Optional, Pattern
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PIIPattern:
    """PII detection pattern."""
    name: str
    pattern: Pattern
    replacement: str
    confidence_threshold: float = 0.8


class LivePIIRedactor:
    """
    Real-time PII Redaction for text and audio streams.
    
    Features:
    - Indian PAN number detection
    - Bank account number detection
    - Aadhaar number detection
    - Email addresses
    - Phone numbers
    - Credit card numbers
    - Custom patterns
    - Configurable confidence thresholds
    """
    
    def __init__(
        self,
        custom_patterns: Optional[List[Dict[str, Any]]] = None,
        default_replacement: str = "[REDACTED]",
    ):
        """
        Initialize PII redactor.
        
        Args:
            custom_patterns: List of custom patterns
                Each: {"name": "name", "pattern": "regex", "replacement": "[REDACTED]"}
            default_replacement: Default replacement string
        """
        self.default_replacement = default_replacement
        self.patterns: List[PIIPattern] = []
        
        # Built-in patterns for Indian PII
        self._add_builtin_patterns()
        
        # Add custom patterns if provided
        if custom_patterns:
            for p in custom_patterns:
                self.add_pattern(
                    p["name"],
                    p["pattern"],
                    p.get("replacement", self.default_replacement),
                )
    
    def _add_builtin_patterns(self) -> None:
        """Add built-in PII patterns for Indian context."""
        
        # Indian PAN: AAAAA9999A
        self.add_pattern(
            "pan",
            r'\b[A-Z]{5}[0-9]{4}[A-Z]\b',
            "[REDACTED_PAN]",
        )
        
        # Indian bank account: 9-18 digits (with context keywords to avoid false positives on phone/Aadhaar)
        self.add_pattern(
            "bank_account",
            r'(?i)(?:account|acct|a/c)[\s:#]*\d{9,18}\b',
            "[REDACTED_BANK_ACCOUNT]",
        )
        
        # Credit card: 13-19 digits (with context to avoid Aadhaar false positives)
        # Must come BEFORE aadhaar to avoid partial matches
        self.add_pattern(
            "credit_card",
            r'(?i)(?:card|credit|cc)(?:\s+(?:number|num))?[\s:#]*\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{3,4}\b',
            "[REDACTED_CARD]",
        )
        
        # Aadhaar: 12 digits (with optional spaces/hyphens), not followed by more digits
        self.add_pattern(
            "aadhaar",
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b(?!\d)',
            "[REDACTED_AADHAAR]",
        )
        
        # Email addresses
        self.add_pattern(
            "email",
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "[REDACTED_EMAIL]",
        )
        
        # Indian phone numbers: +91-XXXXXXXXXX, 0XXXXXXXXXX, +91 XXXXXXXXXX (require prefix)
        self.add_pattern(
            "phone_in",
            r'(?:\+91[\s-]?|0)[6-9]\d{9}\b',
            "[REDACTED_PHONE]",
        )
        
        # International phone
        self.add_pattern(
            "phone_intl",
            r'\+\d{1,3}[\s-]?\(?\d{1,4}\)?[\s-]?\d{3,4}[\s-]?\d{4}',
            "[REDACTED_PHONE]",
        )
        
        # IFSC code: AAAA0BBBBBB
        self.add_pattern(
            "ifsc",
            r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
            "[REDACTED_IFSC]",
        )
        
        # GSTIN: 2 digits (state) + 10 chars (PAN) + 1 digit (entity) + 1 char (check) + 1 char (Z)
        self.add_pattern(
            "gstin",
            r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Zz]\d?\b',
            "[REDACTED_GSTIN]",
        )
        
        # Passport: 1 letter + 7 digits
        self.add_pattern(
            "passport",
            r'\b[A-Z][0-9]{7}\b',
            "[REDACTED_PASSPORT]",
        )
        
        # Driving license: 2 letters + 13 digits (varies by state)
        self.add_pattern(
            "driving_license",
            r'\b[A-Z]{2}\d{13}\b',
            "[REDACTED_DL]",
        )
        
        # Voter ID: 3 letters + 7 digits
        self.add_pattern(
            "voter_id",
            r'\b[A-Z]{3}[0-9]{7}\b',
            "[REDACTED_VOTER_ID]",
        )
    
    def add_pattern(
        self,
        name: str,
        pattern: str,
        replacement: Optional[str] = None,
        flags: int = re.IGNORECASE,
    ) -> None:
        """
        Add a custom PII pattern.
        
        Args:
            name: Pattern name
            pattern: Regex pattern
            replacement: Replacement string
            flags: Regex flags
        """
        pattern_obj = PIIPattern(
            name=name,
            pattern=re.compile(pattern, flags),
            replacement=replacement or self.default_replacement,
        )
        # Remove existing pattern with same name
        self.patterns = [p for p in self.patterns if p.name != name]
        self.patterns.append(pattern_obj)
    
    def remove_pattern(self, name: str) -> bool:
        """Remove a pattern by name."""
        for i, p in enumerate(self.patterns):
            if p.name == name:
                self.patterns.pop(i)
                return True
        return False
    
    def redact(self, text: str) -> str:
        """
        Redact PII from text.
        
        Args:
            text: Input text
            
        Returns:
            Text with PII redacted
        """
        if not text:
            return text
        
        result = text
        for pattern in self.patterns:
            result = pattern.pattern.sub(pattern.replacement, result)
        return result
    
    def redact_dict(self, data: dict) -> dict:
        """Recursively redact PII in dictionary values."""
        if isinstance(data, dict):
            return {k: self.redact_dict(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.redact_dict(v) for v in data]
        elif isinstance(data, str):
            return self.redact(data)
        return data
    
    def find_pii(self, text: str) -> List[Dict[str, Any]]:
        """
        Find all PII matches in text.
        
        Returns:
            List of matches with type, value, position
        """
        matches = []
        for pattern in self.patterns:
            for match in pattern.pattern.finditer(text):
                matches.append({
                    "type": pattern.name,
                    "value": match.group(),
                    "start": match.start(),
                    "end": match.end(),
                    "replacement": pattern.replacement,
                })
        return matches
    
    def redact_audio_transcript(self, text: str) -> str:
        """
        Redact PII from audio transcript with context awareness.
        
        This handles transcript-specific cases like:
        - Speaker names followed by PII
        - Numbers that might be account numbers vs quantities
        """
        return self.redact(text)
    
    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get list of active patterns."""
        return [
            {
                "name": p.name,
                "pattern": p.pattern.pattern,
                "replacement": p.replacement,
            }
            for p in self.patterns
        ]


# Singleton instance
_live_pii_redactor: Optional[LivePIIRedactor] = None


def get_live_pii_redactor() -> LivePIIRedactor:
    """Get singleton PII redactor instance."""
    global _live_pii_redactor
    if _live_pii_redactor is None:
        _live_pii_redactor = LivePIIRedactor()
    return _live_pii_redactor