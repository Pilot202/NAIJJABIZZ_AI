# NaijaBiz AI: ML Service API Contract & Handover Guide

This document specifies the exact endpoints, request/response contracts, and headers required for the backend engineer to integrate with the ML service.

---

## 1. Connection & Authentication

- **ML Service Base URL:** `http://localhost:8080` (or your deployed host)
- **Interactive Swagger Docs:** `http://localhost:8080/docs`
- **Required Header:** All requests from the backend must include the shared API key:
  ```http
  X-API-Key: Abiodun5$
  ```
  *(Configured via `ML_API_KEY` in `ml_service/.env`)*

---

## 2. Endpoints Exposed by ML Service (Called by Backend)

### `POST /interpret`
Parses a typed command into a structured action proposal without saving to the DB.

- **Request Headers:** `Content-Type: application/json`, `X-API-Key: ...`
- **Request Body:**
  ```json
  {
    "text": "I just bought 50 bags of rice for 4 million naira",
    "language": "en", 
    "business_id": "optional-business-uuid",
    "catalogue": [
      {"id": "prod_1", "name": "Rice (50kg)"}
    ]
  }
  ```
  *Supported `language` codes:* `"en"` (English), `"yo"` (Yoruba), `"ha"` (Hausa), `"ig"` (Igbo).
- **Response (`200 OK`):**
  ```json
  {
    "intent": "add_inventory",
    "language": "en",
    "transcript": "I just bought 50 bags of rice for 4 million naira",
    "entities": {
      "product": "rice",
      "matched_product_id": "prod_1",
      "matched_product_name": "Rice (50kg)",
      "quantity": 50.0,
      "unit": "bag",
      "total_amount": 4000000.0,
      "unit_cost": 80000.0,
      "customer": null,
      "category": null,
      "paid": null
    },
    "confidence": 0.95,
    "low_confidence": false,
    "missing_fields": [],
    "confirmation_message": "Add 50 bags of Rice (50kg) at ₦80,000 each?"
  }
  ```
- *Possible intents:* `add_inventory`, `record_sale`, `record_expense`, `record_debt_payment`, `query`, `unknown`.

---

### `POST /transcribe`
Transcribes an audio recording into text.

- **Request Headers:** `Content-Type: multipart/form-data`, `X-API-Key: ...`
- **Form Data:**
  - `audio`: binary audio file (`.wav`, `.m4a`, `.mp3`, `.webm`)
  - `language`: `"en"` | `"yo"` | `"ha"` | `"ig"`
- **Response (`200 OK`):**
  ```json
  {
    "transcript": "Mo ra apo iresi marun",
    "language": "yo",
    "confidence": null
  }
  ```

---

### `POST /interpret/audio`
All-in-one endpoint: takes audio, transcribes it, and interprets it into an `ActionProposal`.

- **Request Headers:** `Content-Type: multipart/form-data`, `X-API-Key: ...`
- **Form Data:**
  - `audio`: binary audio file
  - `language`: `"en"` | `"yo"` | `"ha"` | `"ig"`
  - `business_id`: (optional string)
  - `catalogue_json`: (optional JSON string list of `[{"id":"...", "name":"..."}]`)
- **Response (`200 OK`):**
  Same `ActionProposal` JSON object as `/interpret`.

---

### `POST /parse-receipt`
Extracts line items, quantities, prices, and totals from a receipt photo.

- **Request Headers:** `Content-Type: multipart/form-data`, `X-API-Key: ...`
- **Form Data:**
  - `image`: binary image file (`.jpg`, `.png`, `.jpeg`)
  - `business_id`: (optional string)
  - `catalogue_json`: (optional JSON string list)
- **Response (`200 OK`):**
  ```json
  {
    "supplier": "ABC Distributors",
    "items": [
      {
        "name": "Rice",
        "quantity": 10.0,
        "unit": "bag",
        "unit_price": 85000.0,
        "line_total": 850000.0,
        "matched_product_id": "prod_1"
      }
    ],
    "total": 850000.0,
    "currency": "NGN",
    "confidence": 0.9,
    "warnings": [],
    "raw_text": "...",
    "confirmation_message": "I found 1 items with a total of ₦850,000. Add them to your inventory?"
  }
  ```

---

### `POST /ask`
Natural language business Q&A ("How much stock of rice is left?", "Who owes me money?").

- **Request Headers:** `Content-Type: application/json`, `X-API-Key: ...`
- **Request Body:**
  ```json
  {
    "question": "How much rice do I have left?",
    "language": "en",
    "business_id": "optional-uuid",
    "snapshot": {
      "products": [
        {
          "id": "1",
          "name": "Rice",
          "unit": "bag",
          "stock": 17,
          "avg_daily_sales": 2.0
        }
      ]
    }
  }
  ```
  *(Note: If `snapshot` is omitted, the ML service will fetch it automatically using `business_id` from the backend's `GET /ai/snapshot` endpoint).*
- **Response (`200 OK`):**
  ```json
  {
    "answer": "You have 17 bags of Rice left, which is about 8.5 days of stock.",
    "language": "en",
    "facts_used": {
      "stock": [{"product": "Rice", "in_stock": 17, "days_left": 8.5}]
    }
  }
  ```

---

### `POST /insights`
Generates proactive alerts (low stock warnings, sales drops, expense spikes, overdue debts).

- **Request Body:**
  ```json
  {
    "snapshot": { ...BusinessSnapshot... }
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "alerts": [
      {
        "type": "low_stock",
        "severity": "warning",
        "message": "You have only 3 bags of Rice left. At your current sales rate that is about 1.5 days of stock.",
        "product_id": "prod_1"
      }
    ]
  }
  ```

---

### `POST /forecast`
Returns stock days remaining, cash flow projections, health score (0-100), and affordability evaluation.

- **Request Body:**
  ```json
  {
    "snapshot": { ...BusinessSnapshot... },
    "purchase_price": 250000.0
  }
  ```
- **Response (`200 OK`):**
  ```json
  {
    "stock": [
      {
        "product_id": "1",
        "product_name": "Peak Milk",
        "days_left": 3.0,
        "restock_advice": "Restock Peak Milk within 3 days."
      }
    ],
    "avg_monthly_net_cashflow": 600000.0,
    "next_month_net_cashflow": 600000.0,
    "health_score": 78,
    "affordability": {
      "can_afford": true,
      "safe_min": 240000.0,
      "safe_max": 300000.0,
      "explanation": "Based on your average monthly cash flow of ₦600,000, you can spend roughly ₦240,000 to ₦300,000... This purchase fits."
    }
  }
  ```

---

### `GET /health`
Returns service readiness and active backend configurations.

---

## 3. Endpoints Required by ML Service (To be implemented by Backend)

When the ML service needs business context or product catalogues, it makes read-only calls to the main backend:

1. **`GET /products?business_id={id}`**
   - Returns: `[ {"id": "string", "name": "string"} ]`
2. **`GET /ai/snapshot?business_id={id}`**
   - Returns `BusinessSnapshot`:
     ```json
     {
       "business_id": "string",
       "products": [
         {
           "id": "1",
           "name": "Rice",
           "unit": "bag",
           "stock": 25.0,
           "min_stock": 5.0,
           "avg_daily_sales": 2.5,
           "selling_price": 85000.0,
           "cost_price": 80000.0
         }
       ],
       "sales_this_week": 150000.0,
       "avg_weekly_sales": 200000.0,
       "revenue_this_month": 800000.0,
       "revenue_last_month": 750000.0,
       "expenses_this_month": 400000.0,
       "expenses_last_month": 350000.0,
       "monthly_net_cashflow": [300000.0, 400000.0, 400000.0],
       "debts": [
         {
           "customer": "Musa",
           "amount": 25000.0,
           "days_outstanding": 15
         }
       ]
     }
     ```
