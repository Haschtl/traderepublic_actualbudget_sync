from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any


class PytrRawAmount(BaseModel):
    currency: Optional[str] = None
    value: Optional[float] = None
    fractionDigits: Optional[int] = None


class PytrRaw(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: Optional[str] = None
    timestamp: Optional[str] = None
    title: Optional[str] = None
    amount: Optional[Any] = None
    status: Optional[str] = None
    eventType: Optional[str] = None


class PytrTransaction(BaseModel):
    """Accept mocked and real Trade Republic payloads with additional fields."""

    model_config = ConfigDict(extra="allow")

    # Preprocessed mock fields.
    id_externe: Optional[str] = None
    date: Optional[str] = None
    amount: Optional[Any] = None
    currency: Optional[str] = None
    type: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    instrument: Optional[Any] = None
    raw: Optional[Any] = None

    # Real Trade Republic fields.
    id: Optional[str] = None
    timestamp: Optional[str] = None
    eventType: Optional[str] = None


class ActualTransaction(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    payee: str
    amount: int = Field(..., description="Amount in cents (integer)")
    currency: Optional[str] = "EUR"
    memo: Optional[str] = None
    source_id: Optional[str] = None
    event_type: Optional[str] = None
    cleared: Optional[bool] = True
    pending: Optional[bool] = False
    is_transfer: Optional[bool] = False
    account_key: Optional[str] = "cash"
    transfer_kind: Optional[str] = None
