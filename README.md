# 🥗 Diet Plan Manager

> **Empowering health journeys with data-driven personalized nutrition tracking.** 

A sophisticated full-stack web application designed to help users identify nutritional requirements, select meal plans, and track weekly progress through a responsive interface.

---

## ✨ Key Features

### 🔐 Multi-Channel Authentication
*   **Email & Phone Registration**: Integrated with **SMTP** for email and **SMS Service Gateway** for mobile verification.
*   **Secure OTP Flow**: Time-sensitive 6-digit verification codes to prevent unauthorized access.
*   **Centralized Auth Utility**: Unified session management across all application layers.

### 👤 Personalized Nutrition
*   **BMR Calculation Formula**: Automatically calculates Daily Kcal, Protein, Carbs, and Fat targets based on user body profile (Age, Gender, Weight, Height, Diet Type).
*   **Goal-Driven Plans**: Supports High-Protein, Plant-based, Balanced, and custom dietary structures.

### 🍽️ Meal Selection & Tracking
*   **Meal Discovery**: Curated meal database across multiple categories.
*   **Interactive Weekly Checklist**: Real-time progress tracking of daily consumption.
*   **Dynamic Progress Visualization**: High-end circular progress rings and weekly bar charts.

---

## 🛠️ Technology Stack

| Layer | Technology |
|---|---|
| **Frontend** | Vanilla HTML5, Vanilla CSS3, Modern JavaScript (ES6) |
| **Backend** | Python 3.12+ · Framework-driven API |
| **Database** | SQL-based Relational Database |
| **Async Tasks** | Request Throttling, File-system based Session management |
| **UI Components** | Custom SVG Progress Rings & Data Visualizations |

---

## 🗂️ Project Architecture

```
ROOT/
├── index.html                  # Landing Page with Interactive Components
├── pages/                      # Application Screens
│   ├── dashboard.html          # Performance Analytics
│   ├── weekly-plan.html        # Interactive Tracking Checklist
│   └── register.html           # Multi-step Verification Flow
├── src/
│   ├── auth-header.js          # Shared Authentication Logic
│   ├── styles.css              # Global Design System
│   └── img/                    # Optimized Graphical Assets
└── backend/
    ├── app.py                  # API Entry Point
    ├── routes/                 # Modular API Endpoints
    └── models.py               # Data Schema
```

---

## 🚀 Setup & Installation

### 1. Environment Config
Navigate to the server directory, copy the template and fill in your environmental variables:
```env
SECRET_KEY=secure-random-string
DATABASE_URL=database-connection-string
MAIL_PASSWORD=service-access-token
```

### 2. Automated Launch
The project includes a system-specific script to manage dependency installation and server startup.

### 3. Manual Startup
```bash
pip install -r requirements.txt
python app.py
```
Access the application via the local host address provided in the terminal.

---

## 🔒 Security Summary
*   **Secure Session Handling**: Utilizing protected cookies with standard security flags.
*   **XSS Mitigation**: Safe data rendering for all dynamic user content.
*   **Request Rate Limiting**: Protection against automated access attempts.
*   **Cryptographic Hashing**: Industry-standard password storage algorithms.

---

*Diet Plan Manager — Eat smart. Live better.* 🥗
