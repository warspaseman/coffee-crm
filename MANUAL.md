# Smart Coffee CRM: User Manual

**Version:** 1.0
**Target Audience:** Cashiers, Baristas, Managers

---

## Table of Contents
1.  Getting Started (Вход в систему)<img width="1912" height="1096" alt="image" src="https://github.com/user-attachments/assets/7e284b73-c4cc-4246-8465-c5df18b6c6c4" />
2.  Cashier Mode (Для Кассира)<img width="1908" height="1087" alt="image" src="https://github.com/user-attachments/assets/9f5bfdb8-c668-419c-ad80-fa8d80799272" />
3.  Barista Mode (Для Бариста)<img width="1916" height="1082" alt="image" src="https://github.com/user-attachments/assets/27811144-28d6-48f4-846c-61f6c61613a4" />
4.  Inventory & Auto-Ordering (Склад)<img width="1919" height="1089" alt="image" src="https://github.com/user-attachments/assets/0faec47d-b209-418e-96f4-8e1ca19ebca2" />


---

## 1. Getting Started

### System Access
Open Google Chrome and go to the local server address:
* **URL:** `http://127.0.0.1:8000/`

### Navigation
* **Cashier (POS):** Click "Cashier" to start selling.
* **Barista (KDS):** Click "Barista" to see incoming orders.
* **Admin Panel:** Go to `/admin` to manage the menu and stock.

---

## 2. Cashier Mode (POS)

The interface is designed for high-speed service.

### How to Create an Order
1.  **Select Category:**
    * Click tabs at the top: *Coffee, Tea, Pastry, Cold Drinks*.
2.  **Add Item:**
    * Tap on the product card (e.g., "Latte").
3.  **Customize (Modifiers):**
    * A popup will appear. Ask the customer:
    * **Size:** S (Small), M (Medium), L (Large).
    * **Milk:** Regular, Almond, Oat, Soy.
    * **Syrup:** Vanilla, Caramel, Hazelnut.
4.  **Checkout:**
    * Review the cart on the right side.
    * Click the green **PAY** button.
    * *System Action:* The order is sent to the Kitchen Display immediately.

---

## 3. Barista Mode (KDS)

Replace paper tickets with a digital screen.

### Workflow
1.  **Incoming Orders:**
    * New orders appear automatically as cards.
    * **Yellow Card:** Pending / Preparing.
    * **Content:** Order ID, List of drinks, Special modifiers (e.g., "No Sugar").
2.  **Mark as Ready:**
    * When the drink is ready to serve, click the **Green Checkmark (✔)** on the card.
    * *System Action:* The order disappears from the screen and moves to Archive.

> **Note:** The screen updates automatically every 5 seconds. No need to refresh.

---

## 4. Manager Dashboard

**URL:** `/analytics/`

Use this page to track business performance.

### Key Metrics
* **Total Revenue:** Total money earned.
* **Total Orders:** Number of cups sold.
* **Top Products:** The best-selling items (e.g., "Cappuccino is #1").
* **Sales Chart:** Visual graph of revenue over the last 7 or 30 days.

### AI Prediction (Neural Network)
The system uses Machine Learning to forecast tomorrow's sales.
* Look for the **"AI Forecast"** block.
* **Green Indicator:** Stock is sufficient.
* **Red Indicator:** High demand expected! Check your milk supply.

---

## 5. Inventory & Auto-Ordering

This process happens in the background.

### Automatic Deduction
Every time a Cashier sells a "Latte", the system automatically subtracts:
* -18g Coffee Beans
* -200ml Milk
* -1 Paper Cup

### Auto-Procurement (Smart Email)
You don't need to count stock manually.
1.  **Trigger:** If Milk drops below **5 Liters** (Critical Limit).
2.  **Action:** The system automatically sends an email to the supplier (`supplier@company.com`).
3.  **Result:** A new delivery request is placed without human intervention.

---

### Troubleshooting

| Problem | Solution |
| :--- | :--- |
| **"Network Error"** | Check if the server is running (`python manage.py runserver`). |
| **Email not sent** | Check internet connection and Supplier email in Admin Panel. |
| **Wrong Price** | Go to `/admin` -> `Menu Items` to change prices. |

---

**Technical Support:**
Contact: Nursat Sapar (Developer)
