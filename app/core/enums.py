from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ADMIN = "admin"
    MERCHANT_OWNER = "merchant_owner"
    MERCHANT_STAFF = "merchant_staff"
    SUPPORT = "support"


class MerchantStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class TransactionStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    EXPIRED = "expired"
    SETTLEMENT_PENDING = "settlement_pending"
    SETTLEMENT_PROCESSING = "settlement_processing"
    SETTLEMENT_COMPLETE = "settlement_complete"
    COMPLETED = "completed"
    MANUAL_REVIEW = "manual_review"


class SettlementStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    MANUAL_REVIEW = "manual_review"


class WalletStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"


class PaymentMethodType(StrEnum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    AMEX = "amex"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    OTHER = "other"


class TicketStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"
