# Ashirwad Cleaners Bot & Portal — Project Handover & Context Guide

> **Document Purpose**: This file provides a complete, 360-degree technical and operational briefing for incoming AI agents and developers working on the Ashirwad Cleaners codebase. It captures all architectural decisions, recent bug fixes, data policies, and active issues for a fresh session.

---

## 1. Executive Summary & Environment

* **Business**: Ashirwad Cleaners (Dry cleaning, laundry, steam press, and petrol wash in Paldi, Ahmedabad).
* **Owner/Manager**: Manager Faizan (`+91 84698 42889`). Admin Portal credentials: `admin` / `ashirwad123`.
* **Repository**: `/Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot`
* **Git Remote**: `https://github.com/DhruvVishalPatel/Ashirwad_Cleaners_Whatsapp_Bot.git` (Branch: `main`)
* **Production Server Path**: `/var/www/ashirwad-bot`
* **Production Service**: `systemd` unit `ashirwad-api` (`sudo systemctl restart ashirwad-api`)
* **Local Dev Server**: Runs on `http://127.0.0.1:8000` via FastAPI (`./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`)

---

## 2. Tech Stack & Architecture

### Backend (Python / FastAPI)
* **Framework**: FastAPI (Python 3.14 / 3.11+).
* **Database**: SQLite (`ashirwad.db`), mapped via SQLAlchemy declarative models in [app/models/schemas.py](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/app/models/schemas.py).
* **AI Router**: Google Gemini 2.5/Flash (`app/core/llm_router.py`) for intent classification (`INTENT_PICKUP`, `INTENT_STATUS`, `INTENT_CANCEL_ORDER`, `INTENT_PRICING`, `INTENT_GREETING`, `INTENT_QA`, `INTENT_CHANGE_LANGUAGE`) and multilingual replies in English, Hinglish, and Gujlish.
* **Conversational Agent Engine**: LangGraph state machine (`app/core/graph.py`) with persistent SQLite checkpoints stored in `checkpoints.db`.
* **Outbound WhatsApp Gateway**: Meta WhatsApp Cloud API v19.0 (`app/services/whatsapp_sender.py`).
* **Real-time WebSockets**: `app/api/ws.py` + `app/core/ws_manager.py` broadcasting live dashboard events (`ORDER_CREATED`, `ORDER_STATUS_UPDATED`, `CUSTOMER_UPDATED`, `CHAT_MESSAGE`).

### Frontend (React + Vite Admin Portal)
* **Location**: `frontend/`
* **Styling**: Vanilla CSS (`frontend/src/index.css`) with glassmorphism, responsive POS counter layout, dark/light theme support.
* **Pre-built Assets**: Compiled to `frontend/dist` (`index.html`, `assets/index-*.js`, `assets/index-*.css`).
* **CRITICAL INVARIANT**: The `frontend/dist` directory is **force-tracked in Git** (`git add -f frontend/dist`). The production Ubuntu server does NOT need Node or npm; running `git pull origin main` on the server immediately updates the static assets served by FastAPI at `/`.

---

## 3. Database Schema & Data Invariants

### Tables in `ashirwad.db`
1. **`customers`**: `customer_id`, `name`, `phone_number` (strictly 12-digit E.164: `91XXXXXXXXXX`), `saved_address`, `last_location_gps`, `order_count`, `preferred_language`, `bot_paused`, `created_at`.
2. **`orders`**: `order_id` (numeric string e.g. `"1001"`), `customer_id`, `order_type` (`STORE_DROP` vs `PICKUP`), `status` (`OrderStatus` enum), `item_count`, `total_amount`, `estimated_amount`, `delivery_fee` (₹0 for store drop, ₹30 for pickup unless waived), `points_redeemed`, `payment_status` (`PENDING` vs `PAID`), `payment_mode` (`CASH` vs `UPI`), `disclaimer_accepted`, `runner_id`, `service_category`, `flat_address`, `special_instructions`, `created_at`, `picked_up_at`, `delivered_at`.
3. **`order_items`**: `item_id`, `order_id`, `garment_type`, `service_type`, `quantity`, `special_notes`.
4. **`catalog_items`**: `id`, `service_type`, `item_name`, `price`, `is_variable`, `note`.
5. **`runners`**: `runner_id`, `name`, `phone_number`.
6. **`chat_messages`**: `id`, `customer_id`, `phone_number`, `sender_type` (`CUSTOMER`, `BOT`, `MANAGER`), `message_type`, `content`, `media_url`, `created_at`.
7. **`point_transactions`**: `id`, `customer_id`, `order_id`, `points`, `transaction_type` (`EARNED` vs `REDEEMED`), `created_at`.

### ⚠️ Price Catalog Rule (DO NOT VIOLATE)
* **`price_list.json` is PERMANENTLY DELETED and OBSOLETE.**
* The SQLite table **`catalog_items`** is the **sole single source of truth** for all pricing and services.
* There are **107 catalog items** across exactly 4 service types:
  1. `dry_clean`: 37 garments (e.g. Shirt ₹50, Pant ₹50, Saree ₹200, Blanket ₹250–₹350, Coat ₹200).
  2. `washing`: **6 garments ONLY** (`Kurta` ₹35, `Pant` ₹35, `Payjama` ₹35, `Shirt` ₹35, `T-Shirt` ₹35, `Top` ₹80).
  3. `steam_press`: 22 garments (e.g. Shirt ₹20, Pant ₹20, Saree ₹80, Sherwani ₹100).
  4. `petrol_wash`: 42 garments (all ₹50 flat rate; previously stored as `stain_removal`, now standardized to `petrol_wash`).
* **Shoe Wash does NOT exist in the catalog** and must never be re-introduced to service dropdowns.

### Launch Database Wipe Script
* [clear_test_data.py](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/clear_test_data.py): Wipes all test customers, orders, order items, runners, messages, point transactions, and wipes `checkpoints.db*` while **strictly preserving all 107 `catalog_items`**.

---

## 4. Key Features Implemented Recently

### 1. Order Lifecycle Refactor ([OrderManagement.jsx](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/frontend/src/components/OrderManagement.jsx))
* **Store Drop-off Orders (`STORE_DROP`)** — Strictly **4 States**:
  1. `InStore` (`IN_SHOP`)
  2. `In Cleaning` (`PROCESSING`)
  3. `Ready for Pick Up` (`READY`)
  4. `Picked Up` (`DELIVERED`)
* **Home Delivery Orders (`PICKUP`)** — Strictly **5 States**:
  1. `Pending Pickup` (`PENDING_PICKUP`)
  2. `Received at Store` (`IN_SHOP`) *(The intermediate `Picked Up` state was removed; after Pending Pickup it moves directly to Received at Store)*
  3. `In Cleaning` (`PROCESSING`)
  4. `Ready for Delivery` (`READY`)
  5. `Delivered` (`DELIVERED`)
* Terminal states (`DELIVERED`, `CANCELLED`, `REJECTED`) are permanently locked against modifications.

### 2. POS Garment Combobox & Service Filtering ([CreateOrderModal.jsx](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/frontend/src/components/CreateOrderModal.jsx))
* Custom combobox component (`GarmentCombobox`) with real-time typeahead and browsable dropdown.
* Garment choices are **strictly filtered per service type**:
  * Selecting `Washing` shows only the 6 washable garments.
  * Selecting `Steam Press` shows only the 22 pressable garments.
  * Selecting `Dry Clean` shows 37 garments.
  * Selecting `Petrol Wash` shows 42 garments.
* **Auto-Realigning**: If a user selects "Saree" under Dry Clean and changes the row's service to "Washing", the row automatically switches to the first valid garment for washing (`Shirt` / `Kurta`) at ₹35.

### 3. Business Analytics & Performance Tab ([AnalyticsView.jsx](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/frontend/src/components/AnalyticsView.jsx))
* Dedicated tab in admin portal.
* Timeframe filters: `Daily`, `Weekly`, `Monthly`, `Quarterly`, `Annual`, `All-Time`.
* **Cancelled & Rejected orders are completely excluded** from `total_revenue`, `pending_revenue` (unpaid receivables), channel revenue, and time-bucket trend charts, while staying counted in status metrics.

### 4. Phone Number Normalization ([whatsapp_sender.py](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/app/services/whatsapp_sender.py))
* `format_whatsapp_number(phone: str) -> str`:
  * Normalizes 10-digit Indian numbers (`9876543210`) into Meta E.164 without plus: `919876543210`.
  * Handles numbers starting with 91 (e.g. `9184698428` $\rightarrow$ `919184698428`).
  * Cleans spaces, dashes, `+`, and leading `0`.
  * Applied across `send_text_message`, `send_interactive_buttons`, `send_image_message`, and `create_counter_order`.

---

## 5. Active Critical Issue: WhatsApp Receipt Delivery on New Numbers

### Root Cause
* **Meta WhatsApp Cloud API 24-Hour Customer Care Window**:
  * When a customer sends a message to the business WhatsApp number, a **24-hour session window** opens. Inside this window, the bot can send free-form text messages (`type: "text"`), which is why existing customers receive the order receipt instantly.
  * **When a new walk-in customer is entered via POS dashboard**, they have NOT texted the business in the last 24 hours. Meta **blocks** all `type: "text"` messages to them and returns error:
    `(#131047) Message failed to send because more than 24 hours have passed since the customer last replied to this number. You must use a template message.`

### Solution Roadmap
1. **Meta Pre-Approved Template**:
   * Template Name: `order_confirmation`
   * Category: `UTILITY`
   * Language: `en` (or `en_US`)
   * Body Text:
     ```text
     Namaste {{1}}! 🙏

     Your order #{{2}} has been booked at Ashirwad Cleaners.

     Order Type: {{3}}
     Total Items: {{4}}
     Total Amount: ₹{{5}}
     Payment Status: {{6}}

     Address: G-1, Raj Nagar Complex, Narayan Nagar Road, Paldi.
     Phone: 84698 42889

     We will notify you once your clothes are ready!
     ```
   * Sample variables: `{{1}}`=Dhruv, `{{2}}`=1001, `{{3}}`=Walk-in Store Drop, `{{4}}`=3, `{{5}}`=150, `{{6}}`=Paid.
2. **Backend Fallback in `whatsapp_sender.py`**:
   * Add `send_template_message(to_number, template_name, language_code, components)`.
   * In `send_order_receipt_whatsapp`: If `send_text_message` returns an error code `131047` (or recipient outside 24h window), automatically fall back to `send_template_message` with the order parameters.

---

## 6. Conversational Bot State Flow ([app/core/graph.py](file:///Users/dhruvpatel/PROJECTS/Ashirwad_Cleaners_Bot/app/core/graph.py))

* Multi-turn flow handled by LangGraph:
  1. `ASK_LANGUAGE` $\rightarrow$ sets English, Hinglish, or Gujlish.
  2. `GREETING` $\rightarrow$ options for Schedule Pickup, Check Pricing, Order Status.
  3. `ASK_NAME` / `ASK_ADDRESS` $\rightarrow$ checks Paldi geofencing (must be in Paldi for home pickup; other areas are asked to drop off in-store).
  4. `COLLECTING_ITEMS` $\rightarrow$ NLP parsing of garment type, quantity, and service (tested in `scratch/test_add_clothes.py`).
  5. `SUMMARY_AND_CONFIRMATION` $\rightarrow$ displays itemized order, delivery fee (waived on 4+ monthly orders), points redemption.
  6. `ORDER_PLACED` $\rightarrow$ stores in `orders`, broadcasts via WebSocket.

---

## 7. Deployment Runbook

After making any code changes in this workspace:

1. **Build frontend assets** (if any file in `frontend/src/` changed):
   ```bash
   cd frontend
   npm run build
   cd ..
   ```
2. **Commit and push to remote**:
   ```bash
   git add -f frontend/dist
   git add .
   git commit -m "your descriptive commit message"
   git push origin main
   ```
3. **Apply on Production Server**:
   ```bash
   cd /var/www/ashirwad-bot
   git pull origin main
   sudo systemctl restart ashirwad-api
   ```
4. **Inspect Production Server Logs**:
   ```bash
   journalctl -u ashirwad-api -n 50 --no-pager
   tail -n 50 /var/www/ashirwad-bot/logs/bot.log
   ```

---
*Created on 2026-10-12. Verified up to commit `8e9ebb9`.*
