"""Shared contract between ML, backend and frontend. Agree on changes here with the whole team."""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Language(str, Enum):
    en = "en"  # English (Nigerian-accented)
    yo = "yo"  # Yoruba
    ha = "ha"  # Hausa
    ig = "ig"  # Igbo


class Intent(str, Enum):
    add_inventory = "add_inventory"
    record_sale = "record_sale"
    record_expense = "record_expense"
    record_debt_payment = "record_debt_payment"
    query = "query"
    unknown = "unknown"


class CatalogueItem(BaseModel):
    id: str
    name: str


class Entities(BaseModel):
    product: Optional[str] = None               # what the merchant said
    matched_product_id: Optional[str] = None    # catalogue match, if any
    matched_product_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None                  # bag, carton, bottle...
    total_amount: Optional[float] = None        # naira
    unit_cost: Optional[float] = None           # naira per unit (add_inventory)
    customer: Optional[str] = None
    category: Optional[str] = None              # expense category
    paid: Optional[bool] = None                 # False = sold on credit


class ActionProposal(BaseModel):
    """What the AI understood. Never written to the database until the merchant confirms."""
    intent: Intent
    language: Language
    transcript: str
    entities: Entities = Field(default_factory=Entities)
    confidence: float = Field(ge=0.0, le=1.0)
    low_confidence: bool = False                # True -> ask merchant to repeat/edit
    missing_fields: List[str] = Field(default_factory=list)
    confirmation_message: str = ""


# ---- Transcription ----
class TranscribeResponse(BaseModel):
    transcript: str
    language: Language
    confidence: Optional[float] = None


# ---- Interpret ----
class InterpretRequest(BaseModel):
    text: str
    language: Language = Language.en
    business_id: Optional[str] = None
    catalogue: List[CatalogueItem] = Field(default_factory=list)


# ---- Receipt ----
class ReceiptItem(BaseModel):
    name: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price: Optional[float] = None
    line_total: Optional[float] = None
    matched_product_id: Optional[str] = None


class ReceiptResponse(BaseModel):
    supplier: Optional[str] = None
    items: List[ReceiptItem] = Field(default_factory=list)
    total: Optional[float] = None
    currency: str = "NGN"
    confidence: float = 0.0
    warnings: List[str] = Field(default_factory=list)
    raw_text: str = ""
    confirmation_message: str = ""


# ---- Business snapshot (data the backend provides for ask / insights / forecast) ----
class ProductSnapshot(BaseModel):
    id: str
    name: str
    unit: str = "unit"
    stock: float
    min_stock: float = 0
    avg_daily_sales: float = 0
    selling_price: Optional[float] = None
    cost_price: Optional[float] = None


class DebtSnapshot(BaseModel):
    customer: str
    amount: float
    days_outstanding: int = 0


class BusinessSnapshot(BaseModel):
    business_id: Optional[str] = None
    products: List[ProductSnapshot] = Field(default_factory=list)
    sales_this_week: float = 0
    avg_weekly_sales: float = 0                  # average of previous weeks
    revenue_this_month: float = 0
    revenue_last_month: float = 0
    expenses_this_month: float = 0
    expenses_last_month: float = 0
    monthly_net_cashflow: List[float] = Field(default_factory=list)  # oldest -> newest
    debts: List[DebtSnapshot] = Field(default_factory=list)


# ---- Ask My Business ----
class AskRequest(BaseModel):
    question: str
    language: Language = Language.en
    business_id: Optional[str] = None
    snapshot: Optional[BusinessSnapshot] = None  # if omitted, fetched from the backend


class AskResponse(BaseModel):
    answer: str
    language: Language
    facts_used: Dict[str, Any] = Field(default_factory=dict)


# ---- Insights / forecast ----
class Alert(BaseModel):
    type: str          # low_stock | sales_drop | expense_growth | overdue_debt
    severity: str      # info | warning | critical
    message: str
    product_id: Optional[str] = None


class InsightsRequest(BaseModel):
    snapshot: BusinessSnapshot


class InsightsResponse(BaseModel):
    alerts: List[Alert]


class ForecastRequest(BaseModel):
    snapshot: BusinessSnapshot
    purchase_price: Optional[float] = None       # for "can I afford X?"


class StockForecast(BaseModel):
    product_id: str
    product_name: str
    days_left: Optional[float] = None
    restock_advice: str = ""


class Affordability(BaseModel):
    can_afford: bool
    safe_min: float
    safe_max: float
    explanation: str


class ForecastResponse(BaseModel):
    stock: List[StockForecast]
    avg_monthly_net_cashflow: Optional[float] = None
    next_month_net_cashflow: Optional[float] = None
    health_score: int
    affordability: Optional[Affordability] = None
