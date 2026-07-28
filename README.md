# 🧺 Ashirwad Cleaners Agent Bot

An intelligent, WhatsApp-based conversational assistant and administration dashboard designed for **Ashirwad Cleaners**, a dry-cleaning, washing, and steam press business. 

The system leverages the Google GenAI SDK (using the `gemini-2.5-flash-lite` model) to understand and process user inputs in multiple languages (English, Hindi, Gujarati, or Hinglish), allowing customers to request pickups, check prices, and track order status directly from WhatsApp.

---

## 🚀 Key Features

### 💬 WhatsApp Assistant Flows
* **Intent Routing**: Automatically routes user messages into conversational flows (Pickup, Status, Pricing) using semantic understanding, or bypasses the LLM using WhatsApp interactive button payloads.
* **Conversational Estimation**: Customers can list garments naturally (e.g., *"3 shirts for washing and a blanket for dry cleaning"*). The AI extracts items, maps them to catalog items, and calculates estimated bills.
* **Loyalty Program**:
  * **Delivery Waiver**: The ₹30 delivery fee is waived for users with 4+ orders within the current calendar month.
  * **Points Rewards**: Customers earn 2 points per item processed upon paying. When a customer reaches $\ge 50$ points, they are prompted to redeem their points for a discount (₹1 per point).
* **Location & Addresses**: Integrates with WhatsApp location pins and saves customer addresses for future orders.
* **Working Hours Guard**: Automatically responds with a friendly "closed" message when messaged outside working hours (9:00 AM to 8:30 PM IST).

### 📊 Admin Dashboard (Streamlit)
* **Real-time Analytics**: Quick view of active orders, pending pickups, and registered customers.
* **Interactive Order Management**:
  * Finalize bill pricing.
  * Advance orders through their lifecycle (`PENDING_PICKUP` ➔ `IN_SHOP` ➔ `PROCESSING` ➔ `READY` ➔ `DELIVERED`).
  * Process order payments and trigger loyalty point awards.
  * Dispatch orders to staff (Runners).
* **Customer & Staff Management**: View user points, edit customer pickup addresses, and register delivery runners.

---

## 🛠️ Tech Stack
* **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Backend Webhook API)
* **Dashboard**: [Streamlit](https://streamlit.io/) (Admin Interface)
* **ORM & Database**: [SQLAlchemy](https://www.sqlalchemy.org/) with SQLite (local database `ashirwad.db`)
* **AI Engine**: [Google GenAI SDK](https://github.com/google/generative-ai-python) (`gemini-2.5-flash-lite`)
* **API Integration**: Meta WhatsApp Cloud API (HTTP calls for messaging and interactive buttons)

---

## 📂 Codebase Structure

```text
├── app/
│   ├── core/
│   │   ├── database.py       # DB engine, SessionLocal, and DB initializer
│   │   ├── llm_router.py     # Gemini client, intent router, and item estimator
│   │   └── state_machine.py  # Thread-safe in-memory session store for WhatsApp conversations
│   ├── flows/
│   │   ├── pickup.py         # Multi-step pickup booking, loyalty points, and address flow
│   │   ├── pricing.py        # Service pricing menu formatting and interaction
│   │   └── status.py         # Checks active orders status for customers
│   ├── models/
│   │   └── schemas.py        # SQLAlchemy Models (Customer, Order, OrderItem, PointTransaction, Runner)
│   ├── services/
│   │   ├── crud.py           # DB helper operations (Customer/Order creation, points logic)
│   │   └── whatsapp_sender.py# Meta WhatsApp Cloud API helper for text and button messages
│   └── main.py               # FastAPI entrypoint containing Webhook endpoints
├── dashboard.py              # Streamlit dashboard admin panel
├── price_list.json           # Catalog of items, categories, base prices, and rules
├── requirements.txt          # Python dependency checklist
└── .env                      # Local environment configuration keys (Git ignored)
```

---

## ⚙️ Configuration (`.env`)

Create a `.env` file in the root directory and add the following keys:

```ini
# Gemini API Key
GEMINI_API_KEY=your_gemini_api_key_here

# Meta WhatsApp Cloud API config (leave blank to run in mock/print mode)
WA_PHONE_NUMBER_ID=your_whatsapp_phone_number_id
WA_ACCESS_TOKEN=your_whatsapp_access_token
VERIFY_TOKEN=your_custom_webhook_verification_token

# Database Configuration (Defaults to SQLite in the root directory if left empty)
DATABASE_URL=sqlite:///./ashirwad.db
```

---

## 🏁 Getting Started

### 1. Prerequisites
Make sure Python 3.10+ is installed on your system.

### 2. Setup Virtual Environment & Install Dependencies
```bash
# Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Run FastAPI Application (Webhook Server)
To start the backend API server with auto-reload:
```bash
uvicorn app.main:app --reload
```
* The API will run at `http://127.0.0.1:8000`.
* The WhatsApp webhook endpoints are exposed at:
  * Verification URL: `GET http://127.0.0.1:8000/webhook`
  * Inbound Payload URL: `POST http://127.0.0.1:8000/webhook`

### 4. Run Streamlit Admin Dashboard
To open the manager panel:
```bash
streamlit run dashboard.py
```
* The dashboard will open in your default browser (typically at `http://localhost:8501`).
