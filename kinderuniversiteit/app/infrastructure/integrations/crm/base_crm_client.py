"""Abstract CRM client — swap in HubSpot, Salesforce, etc. without touching use cases."""
from abc import ABC, abstractmethod


class BaseCRMClient(ABC):
    @abstractmethod
    async def upsert_contact(self, external_id: str, properties: dict) -> dict: ...

    @abstractmethod
    async def log_interaction(self, contact_id: str, summary: str) -> dict: ...
