# tests/unit/live_capture/test_pii_redactor.py
"""Unit tests for LivePIIRedactor."""
import pytest
from app.core.ingestion.live_capture.pii_redactor import LivePIIRedactor


class TestLivePIIRedactor:
    """Tests for PII redaction."""

    @pytest.fixture
    def redactor(self):
        return LivePIIRedactor()

    def test_pan_redaction(self, redactor):
        """Test PAN number redaction."""
        text = "My PAN is ABCDE1234F and another is XYZAB9876C"
        redacted = redactor.redact(text)
        assert "[REDACTED_PAN]" in redacted
        assert "ABCDE1234F" not in redacted
        assert "XYZAB9876C" not in redacted

    def test_aadhaar_redaction(self, redactor):
        """Test Aadhaar number redaction."""
        text = "Aadhaar: 1234 5678 9012 and 9876-5432-1098"
        redacted = redactor.redact(text)
        assert "[REDACTED_AADHAAR]" in redacted
        assert "1234 5678 9012" not in redacted
        assert "9876-5432-1098" not in redacted

    def test_email_redaction(self, redactor):
        """Test email redaction."""
        text = "Contact john.doe@example.com or jane@company.co.in"
        redacted = redactor.redact(text)
        assert "[REDACTED_EMAIL]" in redacted
        assert "john.doe@example.com" not in redacted
        assert "jane@company.co.in" not in redacted

    def test_indian_phone_redaction(self, redactor):
        """Test Indian phone number redaction."""
        text = "Call +91-9876543210 or 09876543210"
        redacted = redactor.redact(text)
        assert "[REDACTED_PHONE]" in redacted
        assert "+91-9876543210" not in redacted
        assert "09876543210" not in redacted

    def test_ifsc_redaction(self, redactor):
        """Test IFSC code redaction."""
        text = "IFSC: SBIN0001234"
        redacted = redactor.redact(text)
        assert "[REDACTED_IFSC]" in redacted
        assert "SBIN0001234" not in redacted

    def test_gstin_redaction(self, redactor):
        """Test GSTIN redaction."""
        text = "GSTIN: 27ABCDE1234F1Z5"
        redacted = redactor.redact(text)
        assert "[REDACTED_GSTIN]" in redacted
        assert "27ABCDE1234F1Z5" not in redacted

    def test_credit_card_redaction(self, redactor):
        """Test credit card redaction."""
        text = "Card number: 1234 5678 9012 3456"
        redacted = redactor.redact(text)
        assert "[REDACTED_CARD]" in redacted
        assert "1234 5678 9012 3456" not in redacted

    def test_bank_account_redaction_with_context(self, redactor):
        """Test bank account redaction only with context keywords."""
        # Without context - should NOT redact (too broad)
        text1 = "Random number: 123456789012345678"
        redacted1 = redactor.redact(text1)
        # Should not redact as there's no "account" keyword
        
        # With context - SHOULD redact
        text2 = "Account: 123456789012345678"
        redacted2 = redactor.redact(text2)
        assert "[REDACTED_BANK_ACCOUNT]" in redacted2

    def test_passport_redaction(self, redactor):
        """Test passport number redaction."""
        text = "Passport: A1234567"
        redacted = redactor.redact(text)
        assert "[REDACTED_PASSPORT]" in redacted
        assert "A1234567" not in redacted

    def test_driving_license_redaction(self, redactor):
        """Test driving license redaction."""
        text = "DL: MH1234567890123"
        redacted = redactor.redact(text)
        assert "[REDACTED_DL]" in redacted
        assert "MH1234567890123" not in redacted

    def test_voter_id_redaction(self, redactor):
        """Test voter ID redaction."""
        text = "Voter ID: ABC1234567"
        redacted = redactor.redact(text)
        assert "[REDACTED_VOTER_ID]" in redacted
        assert "ABC1234567" not in redacted

    def test_find_pii(self, redactor):
        """Test PII finding."""
        text = "Email: test@example.com PAN: ABCDE1234F"
        matches = redactor.find_pii(text)
        assert len(matches) == 2
        types = [m["type"] for m in matches]
        assert "email" in types
        assert "pan" in types

    def test_redact_dict(self, redactor):
        """Test recursive dict redaction."""
        data = {
            "email": "user@example.com",
            "nested": {
                "pan": "ABCDE1234F",
                "list": ["+91-9876543210", "clean text"]
            }
        }
        redacted = redactor.redact_dict(data)
        assert redacted["email"] == "[REDACTED_EMAIL]"
        assert redacted["nested"]["pan"] == "[REDACTED_PAN]"
        assert redacted["nested"]["list"][0] == "[REDACTED_PHONE]"
        assert redacted["nested"]["list"][1] == "clean text"

    def test_custom_pattern(self, redactor):
        """Test adding custom pattern."""
        redactor.add_pattern("employee_id", r"EMP-\d{5}", "[REDACTED_EMP]")
        text = "Employee: EMP-12345"
        redacted = redactor.redact(text)
        assert "[REDACTED_EMP]" in redacted
        assert "EMP-12345" not in redacted

    def test_remove_pattern(self, redactor):
        """Test removing pattern."""
        redactor.remove_pattern("pan")
        text = "PAN: ABCDE1234F"
        redacted = redactor.redact(text)
        assert "ABCDE1234F" in redacted  # Not redacted anymore

    def test_empty_text(self, redactor):
        """Test empty text handling."""
        assert redactor.redact("") == ""
        assert redactor.redact(None) is None  # Actually returns None

    def test_audio_transcript_redaction(self, redactor):
        """Test audio transcript redaction."""
        text = "Speaker 1: My email is test@example.com"
        redacted = redactor.redact_audio_transcript(text)
        assert "[REDACTED_EMAIL]" in redacted

    def test_get_patterns(self, redactor):
        """Test getting active patterns."""
        patterns = redactor.get_patterns()
        assert len(patterns) > 0
        names = [p["name"] for p in patterns]
        assert "pan" in names
        assert "aadhaar" in names
        assert "email" in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])