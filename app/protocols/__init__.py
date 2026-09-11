"""POS protocol registry — UI/catalog codes from client terminal screenshots.

IMPORTANT:
These codes (101.x / 201.x / 202.x) are **selection identifiers** for the Turki POS
sandbox and future processor adapters. They are NOT Visa/Mastercard wire formats,
Verifone proprietary packet layouts, or inventable financial message specs.

Until the client supplies official processor/terminal documentation:
- catalog + sandbox behavior mapping only
- no invented request/response cryptography or host messages
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

Connectivity = Literal["online", "offline", "offline_online", "online_offline", "test"]
SandboxOutcome = Literal[
    "capture",
    "pre_auth",
    "force_post",
    "offline_auth",
    "completion",
    "signature",
]
DigitGroup = int | None  # 4 or 6 when applicable; not a live ISO digit-group wire field


@dataclass(slots=True)
class ProtocolDefinition:
    """Full protocol profile configuration (application-level, not ISO wire)."""

    selection_id: str
    """Unique id sent as protocol_code from the POS UI (e.g. 101.1-4dg)."""

    code: str
    """Canonical protocol number as printed on terminal receipts (e.g. 101.1)."""

    name: str
    description: str
    mode: str  # online | offline_test (maps to payment_mode)
    connectivity: Connectivity
    sandbox_outcome: SandboxOutcome
    version: str = "1.0"
    digit_group: DigitGroup = None
    family: str = "101"
    enabled: bool = True
    documented: bool = False
    """True only when official processor docs are wired; False = sandbox label only."""

    sandbox_only: bool = True
    requires_online_authorization: bool = True
    authorization_mode: str = "sale"
    supported_transaction_types: tuple[str, ...] = (
        "SALE",
        "REFUND",
        "VOID",
        "AUTH",
        "COMPLETION",
    )
    allows_manual_entry: bool = True
    signature_likely: bool = False
    ui_environment_label: str = "Demo"

    @property
    def display_label(self) -> str:
        return f"{self.code} - {self.name}"


@dataclass(slots=True)
class ProtocolRequest:
    transaction_id: str
    amount_minor: int
    currency: str
    payment_token: str
    metadata: dict[str, Any] | None = None


@dataclass(slots=True)
class ProtocolResponse:
    status: str
    provider_reference: str
    authorization_code: str | None = None
    signature_required: bool = False
    raw: dict[str, Any] | None = None


class PaymentProtocolAdapter(Protocol):
    """Extensible adapter — implement from official docs only."""

    def build_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> dict[str, Any]: ...

    def validate_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> None: ...

    def send_request(self, definition: ProtocolDefinition, request: ProtocolRequest) -> ProtocolResponse: ...

    def parse_response(self, payload: dict[str, Any]) -> ProtocolResponse: ...

    def validate_response(self, response: ProtocolResponse) -> None: ...

    def map_status(self, response: ProtocolResponse) -> str: ...


def _p(
    selection_id: str,
    code: str,
    name: str,
    *,
    mode: str,
    connectivity: Connectivity,
    sandbox_outcome: SandboxOutcome,
    digit_group: DigitGroup = None,
    family: str | None = None,
    description: str | None = None,
    enabled: bool = True,
    authorization_mode: str | None = None,
    supported_transaction_types: tuple[str, ...] | None = None,
    requires_online_authorization: bool | None = None,
    allows_manual_entry: bool = True,
    signature_likely: bool = False,
    ui_environment_label: str | None = None,
) -> ProtocolDefinition:
    fam = family or code.split(".", 1)[0]
    desc = description or (
        f"Sandbox mapping for terminal protocol {code} ({name}). "
        "Not a live card-network message until official docs are supplied."
    )
    auth = authorization_mode or {
        "capture": "sale",
        "pre_auth": "pre_auth",
        "force_post": "force_post",
        "offline_auth": "offline_auth",
        "completion": "completion",
        "signature": "offline_auth",
    }.get(sandbox_outcome, "sale")
    online = requires_online_authorization if requires_online_authorization is not None else mode == "online"
    ui = ui_environment_label or ("Simulation" if mode == "offline_test" and sandbox_outcome == "offline_auth" else "Demo")
    types = supported_transaction_types or (
        ("AUTH", "COMPLETION", "VOID")
        if auth in {"pre_auth", "offline_auth"} and code in {"101.6", "201", "201.3"}
        else ("COMPLETION", "VOID")
        if auth == "completion"
        else ("SALE", "REFUND", "VOID", "AUTH", "COMPLETION")
    )
    return ProtocolDefinition(
        selection_id=selection_id,
        code=code,
        name=name,
        description=desc,
        mode=mode,
        connectivity=connectivity,
        sandbox_outcome=sandbox_outcome,
        digit_group=digit_group,
        family=fam,
        enabled=enabled,
        documented=False,
        sandbox_only=True,
        requires_online_authorization=online,
        authorization_mode=auth,
        supported_transaction_types=types,
        allows_manual_entry=allows_manual_entry,
        signature_likely=signature_likely or sandbox_outcome == "signature",
        ui_environment_label=ui,
    )


# Catalog labels derived from client screenshots (vPOS demo + Verifone receipt).
# Missing 101.8/101.9 / 201.4–201.5 / 201.7–201.9 are explicit placeholders.
PROTOCOL_CATALOG: dict[str, ProtocolDefinition] = {
    # Legacy / generic
    "101": _p(
        "101",
        "101",
        "Card present (generic)",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        description="Generic online card-present sandbox path.",
    ),
    "102": _p(
        "102",
        "102",
        "Keyed / manual entry (test)",
        mode="offline_test",
        connectivity="test",
        sandbox_outcome="capture",
        family="102",
        description="Sandbox keyed-entry path — TEST MODE only.",
    ),
    # --- 101.x Online / Cloud (from vPOS "Select Transaction Protocol") ---
    "101.1-6dg": _p(
        "101.1-6dg",
        "101.1",
        "Online 6 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=6,
    ),
    "101.1-4dg": _p(
        "101.1-4dg",
        "101.1",
        "Online 4 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=4,
    ),
    "101.2": _p(
        "101.2",
        "101.2",
        "Cloud Sale 6 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=6,
    ),
    "101.3-6dg": _p(
        "101.3-6dg",
        "101.3",
        "Cloud Purchase 6 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=6,
    ),
    "101.3-4dg": _p(
        "101.3-4dg",
        "101.3",
        "Cloud Purchase 4 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=4,
    ),
    "101.4-6dg": _p(
        "101.4-6dg",
        "101.4",
        "Cloud Purchase 6 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=6,
    ),
    "101.4-4dg": _p(
        "101.4-4dg",
        "101.4",
        "Cloud Purchase 4 DG",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        digit_group=4,
    ),
    "101.5": _p(
        "101.5",
        "101.5",
        "MO/TO Cloud",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        description="Mail Order / Telephone Order cloud path (sandbox label only).",
    ),
    "101.6": _p(
        "101.6",
        "101.6",
        "Pre-Auth",
        mode="online",
        connectivity="online",
        sandbox_outcome="pre_auth",
    ),
    "101.7": _p(
        "101.7",
        "101.7",
        "Force Post",
        mode="online",
        connectivity="online",
        sandbox_outcome="force_post",
    ),
    "101.8": _p(
        "101.8",
        "101.8",
        "Reserved (awaiting docs)",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        description="Placeholder 101.8 — enable semantics only with official protocol docs.",
    ),
    "101.9": _p(
        "101.9",
        "101.9",
        "Reserved (awaiting docs)",
        mode="online",
        connectivity="online",
        sandbox_outcome="capture",
        description="Placeholder 101.9 — enable semantics only with official protocol docs.",
    ),
    # --- 201.x Offline / hybrid (vPOS + Verifone receipt) ---
    "201": _p(
        "201",
        "201",
        "Offline Auth",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.1": _p(
        "201.1",
        "201.1",
        "Cloud Completion",
        mode="offline_test",
        connectivity="offline_online",
        sandbox_outcome="completion",
        family="201",
    ),
    "201.2": _p(
        "201.2",
        "201.2",
        "Offline Post",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.3": _p(
        "201.3",
        "201.3",
        "Offline 6 DG",
        mode="offline_test",
        connectivity="online_offline",
        sandbox_outcome="signature",
        digit_group=6,
        family="201",
    ),
    "201.4": _p(
        "201.4",
        "201.4",
        "Reserved (awaiting docs)",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.5": _p(
        "201.5",
        "201.5",
        "Reserved (awaiting docs)",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.6": _p(
        "201.6",
        "201.6",
        "Offline-Online",
        mode="offline_test",
        connectivity="offline_online",
        sandbox_outcome="offline_auth",
        family="201",
        description="Listed active on Verifone protocol receipt (sandbox mapping only).",
    ),
    "201.7": _p(
        "201.7",
        "201.7",
        "Reserved (awaiting docs)",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.8": _p(
        "201.8",
        "201.8",
        "Reserved (awaiting docs)",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    "201.9": _p(
        "201.9",
        "201.9",
        "Reserved (awaiting docs)",
        mode="offline_test",
        connectivity="offline",
        sandbox_outcome="offline_auth",
        family="201",
    ),
    # --- 202.x from Verifone receipt ---
    "202.2": _p(
        "202.2",
        "202.2",
        "Offline-Online",
        mode="offline_test",
        connectivity="offline_online",
        sandbox_outcome="offline_auth",
        family="202",
    ),
    "202.5": _p(
        "202.5",
        "202.5",
        "Offline-Online",
        mode="offline_test",
        connectivity="offline_online",
        sandbox_outcome="offline_auth",
        family="202",
    ),
    "202.9": _p(
        "202.9",
        "202.9",
        "Offline-Online",
        mode="offline_test",
        connectivity="offline_online",
        sandbox_outcome="offline_auth",
        family="202",
    ),
}


def get_protocol(code_or_selection_id: str) -> ProtocolDefinition:
    key = code_or_selection_id.strip()
    if key in PROTOCOL_CATALOG and PROTOCOL_CATALOG[key].enabled:
        return PROTOCOL_CATALOG[key]
    # Allow canonical code when unique or prefer first 6dg / first listed variant.
    matches = [p for p in PROTOCOL_CATALOG.values() if p.enabled and p.code == key]
    if not matches:
        raise KeyError(f"Unknown or disabled protocol: {code_or_selection_id}")
    preferred = next((p for p in matches if p.digit_group == 6), None)
    return preferred or matches[0]


def list_protocols(
    *,
    mode: str | None = None,
    family: str | None = None,
    transaction_type: str | None = None,
) -> list[ProtocolDefinition]:
    items = [item for item in PROTOCOL_CATALOG.values() if item.enabled]
    if mode:
        items = [i for i in items if i.mode == mode]
    if family:
        items = [i for i in items if i.family == family]
    if transaction_type:
        tt = transaction_type.strip().upper()
        filtered = [i for i in items if tt in i.supported_transaction_types]
        items = filtered or items

    def _sort_key(p: ProtocolDefinition) -> tuple:
        try:
            fam_n = int(p.family) if p.family.isdigit() else 999
        except ValueError:
            fam_n = 999
        dg = 0 if p.digit_group == 6 else (1 if p.digit_group == 4 else 2)
        return (fam_n, p.code, dg, p.selection_id)

    return sorted(items, key=_sort_key)


def validate_protocol_selection(selection_id: str, transaction_type: str) -> ProtocolDefinition:
    """Raise KeyError / ValueError if profile cannot be used for the txn type."""
    definition = get_protocol(selection_id)
    tt = transaction_type.strip().upper()
    if not definition.enabled:
        raise ValueError(f"Protocol {definition.code} is disabled")
    if tt not in definition.supported_transaction_types:
        raise ValueError(f"Protocol {definition.display_label} does not support {tt}")
    if definition.documented is False and definition.sandbox_only is False:
        raise ValueError("Undocumented non-sandbox protocol blocked")
    return definition

