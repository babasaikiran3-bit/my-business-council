"""Account, identity, child-profile, and consent storage (Phase 2).

JSON-backed and partitioned per ``user_id``, behind a small store so a Postgres
implementation can replace it later. Holds the data the conversation store does not:

- accounts/{user_id}.json — display name, linked OAuth providers, child profiles,
  and itemized PIPA consents.
- identities/{provider}__{sha256(provider_user_id)}.json — reverse index for O(1)
  "which account owns this Kakao/Naver identity" lookups (the basis of account linking).

The OAuth identity links to the caller's EXISTING (anonymous) ``user_id`` on first
sign-in — merge-in-place — so anonymous history is preserved, per the consensus plan.
"""

import asyncio
import hashlib
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import DATA_DIR
from .storage_backend import (
    KeyedLocks,
    StorageCorruptionError,
    _atomic_write_json,
    _read_json_or_quarantine,
)

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9_-]+$")
KST = timezone(timedelta(hours=9))

# The itemized PIPA consents (see plan §11.2). Health + child-data + cross-border
# are the legally meaningful ones; marketing is optional.
REQUIRED_CONSENTS = ["sensitive_health", "child_data_by_guardian", "cross_border_transfer"]
ALL_CONSENTS = REQUIRED_CONSENTS + ["marketing"]


def _is_safe_id(value: str) -> bool:
    return bool(value) and bool(_SAFE_ID_RE.match(value))


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def age_days_from_birthdate(birthdate_iso: str, today: Optional[date] = None) -> Optional[int]:
    """Whole days from birthdate (YYYY-MM-DD) to today (KST). None if unparseable/future."""
    try:
        born = date.fromisoformat(birthdate_iso)
    except (ValueError, TypeError):
        return None
    if today is None:
        today = datetime.now(KST).date()
    delta = (today - born).days
    return delta if delta >= 0 else None


class AccountStore:
    def __init__(self, data_dir: str = DATA_DIR):
        self.base = Path(data_dir)
        # Per-key locks: account:<user_id> and identity:<provider>:<id>.
        self._lock_for = KeyedLocks()

    # --- paths ---
    def _account_path(self, user_id: str) -> Path:
        if not _is_safe_id(user_id):
            raise ValueError("invalid user_id")
        return self.base / "accounts" / f"{user_id}.json"

    def _identity_path(self, provider: str, provider_user_id: str) -> Path:
        if not _is_safe_id(provider):
            raise ValueError("invalid provider")
        digest = hashlib.sha256(provider_user_id.encode()).hexdigest()
        return self.base / "identities" / f"{provider}__{digest}.json"

    # --- accounts ---
    def get_account(self, user_id: str) -> Optional[Dict[str, Any]]:
        path = self._account_path(user_id)
        if not path.exists():
            return None
        try:
            return _read_json_or_quarantine(path)
        except StorageCorruptionError:
            # A corrupt account file is treated as "no account" (recoverable: a fresh
            # OAuth login re-links). Never 500 the auth surface on it.
            return None

    def _save_account(self, account: Dict[str, Any]) -> None:
        _atomic_write_json(self._account_path(account["user_id"]), account)

    def ensure_account(self, user_id: str) -> Dict[str, Any]:
        account = self.get_account(user_id)
        if account is None:
            account = {
                "user_id": user_id,
                "display_name": None,
                "created_at": _utcnow_iso(),
                "providers": [],
                "children": [],
                "consents": {},
            }
            self._save_account(account)
        return account

    def is_authenticated(self, user_id: str) -> bool:
        account = self.get_account(user_id)
        return bool(account and account.get("providers"))

    # --- identities / linking ---
    def find_user_by_identity(self, provider: str, provider_user_id: str) -> Optional[str]:
        path = self._identity_path(provider, provider_user_id)
        if not path.exists():
            return None
        try:
            return _read_json_or_quarantine(path).get("user_id")
        except StorageCorruptionError:
            return None

    async def link_identity(
        self, current_user_id: str, provider: str, provider_user_id: str,
        display_name: Optional[str] = None,
    ) -> str:
        """Resolve the account for an OAuth identity, linking it in place if new.

        - If the identity already maps to an account → return THAT user_id (returning login).
        - Otherwise → attach it to the caller's current (anonymous) account and return it,
          so the caller's existing history carries over.

        Serialised on the IDENTITY key (not user_id): the real race is two concurrent
        first-logins for the SAME provider identity (different anon sessions) both creating
        the index. We re-check inside the lock and write the account BEFORE the identity
        index, so a crash leaves at worst a missing index (re-linkable) — never an index
        pointing at an account that never recorded the provider.
        """
        ident_key = f"identity:{provider}:{provider_user_id}"
        async with self._lock_for(ident_key):
            existing = self.find_user_by_identity(provider, provider_user_id)
            if existing:
                return existing

            async with self._lock_for(f"account:{current_user_id}"):
                account = self.ensure_account(current_user_id)
                if not any(p["provider"] == provider for p in account["providers"]):
                    account["providers"].append({"provider": provider, "provider_user_id": provider_user_id})
                if display_name and not account.get("display_name"):
                    account["display_name"] = display_name
                await asyncio.to_thread(self._save_account, account)

            await asyncio.to_thread(
                _atomic_write_json,
                self._identity_path(provider, provider_user_id),
                {"user_id": current_user_id, "provider": provider, "provider_user_id": provider_user_id},
            )
            return current_user_id

    # --- child profiles ---
    def list_children(self, user_id: str) -> List[Dict[str, Any]]:
        account = self.get_account(user_id)
        return account.get("children", []) if account else []

    def get_child(self, user_id: str, child_id: str) -> Optional[Dict[str, Any]]:
        for child in self.list_children(user_id):
            if child["id"] == child_id:
                return child
        return None

    async def add_child(self, user_id: str, name: str, birthdate: str) -> Dict[str, Any]:
        # Name is OPTIONAL (the UI shows "우리 아이" when blank); only the birthdate is
        # required for the safety-relevant age. Reject over-long or control-char names.
        name = (name or "").strip()
        if len(name) > 40 or any(ord(c) < 32 for c in name):
            raise ValueError("invalid name")
        if age_days_from_birthdate(birthdate) is None:
            raise ValueError("invalid birthdate")
        async with self._lock_for(f"account:{user_id}"):
            account = self.ensure_account(user_id)
            child = {"id": uuid.uuid4().hex, "name": name, "birthdate": birthdate}
            account["children"].append(child)
            await asyncio.to_thread(self._save_account, account)
        return child

    async def update_child(
        self, user_id: str, child_id: str,
        name: Optional[str] = None, birthdate: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Patch a child's name and/or birthdate. Returns the updated child, or None if absent."""
        async with self._lock_for(f"account:{user_id}"):
            account = self.get_account(user_id)
            if not account:
                return None
            child = next((c for c in account["children"] if c["id"] == child_id), None)
            if child is None:
                return None
            if name is not None:
                name = name.strip()
                if len(name) > 40 or any(ord(c) < 32 for c in name):
                    raise ValueError("invalid name")
                child["name"] = name
            if birthdate is not None:
                if age_days_from_birthdate(birthdate) is None:
                    raise ValueError("invalid birthdate")
                child["birthdate"] = birthdate
            await asyncio.to_thread(self._save_account, account)
            return child

    async def delete_child(self, user_id: str, child_id: str) -> bool:
        async with self._lock_for(f"account:{user_id}"):
            account = self.get_account(user_id)
            if not account:
                return False
            before = len(account["children"])
            account["children"] = [c for c in account["children"] if c["id"] != child_id]
            if len(account["children"]) == before:
                return False
            await asyncio.to_thread(self._save_account, account)
        return True

    # --- consents ---
    async def record_consents(self, user_id: str, kinds: List[str], version: str) -> Dict[str, Any]:
        async with self._lock_for(f"account:{user_id}"):
            account = self.ensure_account(user_id)
            now = _utcnow_iso()
            for kind in kinds:
                if kind in ALL_CONSENTS:
                    account["consents"][kind] = {"version": version, "granted_at": now}
            await asyncio.to_thread(self._save_account, account)
            return account["consents"]

    def get_consents(self, user_id: str) -> Dict[str, Any]:
        account = self.get_account(user_id)
        return account.get("consents", {}) if account else {}

    def has_required_consents(self, user_id: str) -> bool:
        consents = self.get_consents(user_id)
        return all(k in consents for k in REQUIRED_CONSENTS)


accounts = AccountStore()
