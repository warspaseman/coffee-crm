<div align="center">

# Smart Coffee CRM
### Next-Gen Inventory Automation System

![Python](https://img.shields.io/badge/python-3.9+-blue.svg?style=flat&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/django-4.2-092E20.svg?style=flat&logo=django&logoColor=white)
![Chart.js](https://img.shields.io/badge/chart.js-F5788D.svg?style=flat&logo=chart.js&logoColor=white)
![Status](https://img.shields.io/badge/status-active-success.svg?style=flat)

</div>

**Smart Coffee CRM** is an enterprise-grade solution designed to bridge the gap between simple POS terminals and complex ERP systems. It provides a seamless flow of data from the cashier's tablet directly to the warehouse and financial reports.

The core philosophy of this project is **Automation First**. The system autonomously manages inventory levels, ensuring that business operations never stop due to a lack of ingredients, thanks to its intelligent **Auto-Procurement Module**.

---

## Key Features

### Point of Sale (POS)
* **Dynamic Interface:** Fast, responsive UI designed for high-traffic environments.
* **Smart Cart:** Automatic calculation of totals and complex orders.
* **Modifier Support:** Handles customizations (e.g., "Latte + Almond Milk") effortlessly.

### Intelligent Inventory
* **Recipe Engine:** Each product is linked to a technological map. Selling a product automatically deducts specific ingredients (beans, milk, cups) from the warehouse.
* **Atomic Transactions:** Uses `transaction.atomic` to ensure data integrity during simultaneous orders.
* **Auto-Procurement:** The system monitors stock levels in real-time. If an ingredient hits the **Critical Limit**, an official **Purchase Order (PO)** is automatically generated and emailed to the specific supplier via SMTP.

### Kitchen Display System (KDS)
* **Digital Workflow:** Replaces paper tickets. Orders move from `Pending` → `Ready` → `Completed`.
* **Real-time Updates:** Baristas see new orders instantly.

### Financial Analytics
* **Interactive Dashboard:** Visualized data powered by **Chart.js**.
* **Metrics:** Real-time Revenue, Order Count, and Sales Reports.
* **Time-Series Data:** Filter analytics by Week, Month, Quarter, or Year.

---

## Tech Stack

| Component | Technology | Description |
| :--- | :--- | :--- |
| **Backend** | Python / Django | Core logic, ORM, API, SMTP |
| **Frontend** | HTML5 / CSS3 | Responsive UI Design |
| **Scripting** | JavaScript (ES6) | Async Fetch API, DOM Manipulation |
| **Database** | SQLite / PostgreSQL | Relational Data Storage |
| **Visualization** | Chart.js | Data Rendering |

---

## Project Structure

```
coffee-core/
├── coffee/                 # Main Application
│   ├── migrations/         # Database Migrations
│   ├── templates/          # HTML Files (POS, KDS, Analytics)
│   ├── admin.py            # Admin Panel Configuration
│   ├── models.py           # Database Schema & Business Logic
│   ├── views.py            # API Endpoints & Controllers
│   └── urls.py             # Routing
├── coffee_core/            # Project Settings
│   ├── settings.py         # Config (Email, DB, Apps)
│   └── urls.py             # Main Routing
├── db.sqlite3              # Database File
├── manage.py               # Django Command Line Utility
└── requirements.txt        # Python Dependencies
```


Installation & Setup
1. Clone the repository
Bash
```
git clone [https://github.com/your-username/coffee-crm.git](https://github.com/your-username/coffee-crm.git)
cd coffee-crm
```
2. Set up Virtual Environment
Bash
```
python -m venv venv
```
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate
3. Install Dependencies
Bash
```
pip install -r requirements.txt
```
4. Database Setup
Bash
```
python manage.py makemigrations
python manage.py migrate
5. Create Admin User
```
Bash

python manage.py createsuperuser
6. Run Server
Bash

python manage.py runserver
Access the application at http://127.0.0.1:8000/.

Configuration (SMTP)
To enable the Auto-Order feature, configure your email settings in coffee_core/settings.py.

Python
```
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-16-digit-app-password'
```
Roadmap
Basic POS & Inventory
Auto-Ordering via Email
Financial Analytics
Auto-Prediction system

<div align="center">
Developed by Nursat Sapar and Suiinbaiissaui Kabzakiruly

Astana IT University | Cybersecurity Major
</div>
