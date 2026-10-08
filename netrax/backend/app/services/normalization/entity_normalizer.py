"""
Entity Normalization Service — normalizes entity values while preserving originals.
Stores both value and normalized_value.
"""

import re
import logging

logger = logging.getLogger(__name__)


class EntityNormalizationService:
    """
    Normalizes entity values for consistent comparison and deduplication.
    The original value is always preserved.
    """

    def normalize(self, entity_type: str, value: str) -> str:
        """
        Normalize an entity value based on its type.
        
        Args:
            entity_type: The type of entity (PERSON, PHONE, etc.)
            value: The raw extracted value.
            
        Returns:
            Normalized value string.
        """
        normalizer = self._normalizers.get(entity_type, self._default_normalize)
        try:
            return normalizer(value)
        except Exception as e:
            logger.warning(f"Normalization failed for {entity_type}='{value}': {e}")
            return value.strip().lower()

    @property
    def _normalizers(self):
        return {
            "PERSON": self._normalize_person,
            "PHONE": self._normalize_phone,
            "EMAIL": self._normalize_email,
            "LOCATION": self._normalize_location,
            "ORGANIZATION": self._normalize_organization,
            "VEHICLE": self._normalize_vehicle,
            "CASE": self._normalize_case,
            "DATE": self._normalize_date,
            "DEVICE": self._normalize_device,
            "ACCOUNT": self._normalize_account,
        }

    def _normalize_person(self, value: str) -> str:
        """Normalize person names: lowercase, collapse whitespace, strip titles."""
        name = value.strip().lower()
        # Collapse multiple spaces
        name = re.sub(r'\s+', ' ', name)
        # Remove common titles
        name = re.sub(r'^(mr\.?|mrs\.?|ms\.?|dr\.?|shri\.?|smt\.?|sh\.?)\s+', '', name, flags=re.IGNORECASE)
        return name.strip()

    def _normalize_phone(self, value: str) -> str:
        """Normalize phone numbers: digits only, strip country code prefix."""
        digits = re.sub(r'[^\d]', '', value)
        # If starts with 91 and has 12 digits, strip country code
        if len(digits) == 12 and digits.startswith('91'):
            digits = digits[2:]
        # If starts with 0 and has 11 digits, strip leading 0
        if len(digits) == 11 and digits.startswith('0'):
            digits = digits[1:]
        return digits

    def _normalize_email(self, value: str) -> str:
        """Normalize email: lowercase, strip whitespace."""
        return value.strip().lower()

    def _normalize_location(self, value: str) -> str:
        """Normalize location: lowercase, collapse whitespace."""
        location = value.strip().lower()
        location = re.sub(r'\s+', ' ', location)
        return location

    def _normalize_organization(self, value: str) -> str:
        """Normalize organization: lowercase, collapse whitespace."""
        org = value.strip().lower()
        org = re.sub(r'\s+', ' ', org)
        return org

    def _normalize_vehicle(self, value: str) -> str:
        """Normalize vehicle registration: uppercase, remove spaces/hyphens."""
        vehicle = re.sub(r'[\s\-]', '', value).upper()
        return vehicle

    def _normalize_case(self, value: str) -> str:
        """Normalize case/FIR numbers: uppercase, standardize separators."""
        case_num = value.strip().upper()
        case_num = re.sub(r'\s+', '-', case_num)
        return case_num

    def _normalize_date(self, value: str) -> str:
        """Normalize dates: keep as-is for now (complex date parsing deferred)."""
        return value.strip()

    def _normalize_device(self, value: str) -> str:
        """Normalize device IDs (IMEI): digits only."""
        return re.sub(r'[^\d]', '', value)

    def _normalize_account(self, value: str) -> str:
        """Normalize account numbers: digits only."""
        return re.sub(r'[^\d]', '', value)

    def _default_normalize(self, value: str) -> str:
        """Default normalization: lowercase and strip."""
        return value.strip().lower()
