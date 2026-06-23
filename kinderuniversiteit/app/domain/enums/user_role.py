from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"     # full access: settings, documents, all conversations
    AGENT = "agent"     # handle escalations, view assigned conversations
    VIEWER = "viewer"   # read-only dashboards and analytics
