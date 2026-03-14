DIET PLAN MANAGER – TECHNICAL OVERVIEW
==================================================

Empowering health journeys with data-driven personalized nutrition tracking.

A sophisticated full-stack web application designed to help users identify 
nutritional requirements, select meal plans, and track weekly progress through 
a responsive interface.

KEY FEATURES
--------------------------------------------------

1. Multi-Channel Authentication
   - Email & Phone Registration: Integrated with SMTP and SMS Service Gateway.
   - Secure OTP Flow: Time-sensitive 6-digit verification codes.
   - Centralized Auth Utility: Shared session management across all layers.

2. Personalized Nutrition
   - BMR Calculation Formula: Calculates Daily Kcal, Protein, Carbs, and Fat 
     based on body profile (Age, Gender, Weight, Height, Diet Type).
   - Goal-Driven Plans: Supports High-Protein, Plant-based, Balanced, and more.

3. Meal Selection & Tracking
   - Meal Discovery: Curated meal database.
   - Interactive Weekly Checklist: Real-time consumption tracking.
   - Dynamic Visualization: High-end progress rings and charts.

TECHNOLOGY STACK
--------------------------------------------------

- Frontend: Vanilla HTML5, CSS3, Modern JavaScript (ES6)
- Backend: Python 3.12+ · Framework-driven API
- Database: SQL-based Relational Database
- Services: Request Throttling, File-system based Session management
- UI: Custom SVG Progress Rings & Data Visualizations

PROJECT ARCHITECTURE
--------------------------------------------------

ROOT/
├── index.html          # Landing Page
├── pages/              # Application Screens (Analytics, Checklist, Flow)
├── src/                # Shared Logic & Assets
└── backend/            # API Server (Routes, Models, Config)

SETUP & INSTALLATION
--------------------------------------------------

1. Environment Config
   Navigate to the server directory, configuration includes:
   - SECRET_KEY
   - DATABASE_URL
   - MAIL_PASSWORD

2. Automated Launch
   The project includes a launch script for automated setup and execution.

3. Manual Startup
   pip install -r requirements.txt
   python app.py

   Open the local host address in your web browser.

SECURITY
--------------------------------------------------
- Secure Session handling (Protected Cookies)
- XSS Protection on dynamic displays
- Rate Limiting on sensitive endpoints
- Cryptographic Password Hashing

--------------------------------------------------
Diet Plan Manager — Eat smart. Live better. 🥗
