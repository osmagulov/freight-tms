# 🚛 Freight TMS — Obsidian Edition v4.0

### Система управления грузоперевозками следующего поколения

Freight TMS — это мощная SaaS-платформа для управления автопарком (100+ водителей, 200+ грузовиков) на международных маршрутах (CN↔KZ, KZ↔RU, Турция, Грузия). Платформа сочетает в себе надежность бэкенда на Python/FastAPI и премиальный пользовательский интерфейс в стиле **Obsidian**.

![Obsidian Design System](https://img.shields.io/badge/UI/UX-Obsidian--Premium-3b82f6?style=for-the-badge)
![Tech Stack](https://img.shields.io/badge/Stack-Python_3.11_|_HTMX_|_Tailwind_|_PostgreSQL-0ea5e9?style=for-the-badge)

---

## ✨ Основные возможности (Phase 3 Modernized)

### 📊 Аналитика и Контроль (Admin Panel)
- **Интеллектуальный Дашборд:** Визуализация прибыли, расходов (EBITDA) и активности парка в реальном времени.
- **Антифрод Система:** Сверхточная автоматическая сверка транзакций АЗС с чеками водителей (по времени и гео-позиции).
- **Экипажи и Флот:** Высокоплотное управление водителями, документами и состоянием транспорта.
- **Экспорт Документов:** Генерация CMR, путевых листов и финансовых актов за 1 клик.

### 📱 Мобильное PWA (Для Водителей)
- **Dashboard:** Удобные задачи, контроль текущего рейса и быстрые запросы диспетчеру.
- **Смарт-Расходы:** Загрузка чеков с анимированным AI-сканированием и фиксацией литража.
- **Отчеты о поломках:** Мгновенная отправка данных о неисправностях в отдел ТО.
- **Мультиязычность:** Полная поддержка RU, KZ, CN.

---

## 🛠 Технологический стек

- **Backend:** [FastAPI](https://fastapi.tiangolo.com/) (Async)
- **Database:** PostgreSQL (Async pg) + Alembic migrations
- **Frontend Admin:** Jinja2 + **HTMX** (для динамики без JS-перегрузки)
- **PWA Style:** Custom CSS Architecture (High Performance) + Obsidian Design Patterns
- **DevOps:** Railway Deployment
- **Bot:** python-telegram-bot v22+ (FSM Persistence)
- **Storage:** Cloudflare R2 (S3 compatible)

---

## 🚀 Быстрый старт (Development)

1. **Установка зависимостей:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Запуск сервера:**
   ```bash
   uvicorn src.main:app --reload --port 8000
   ```

3. **Локальные ссылки:**
   - Панель управления: [http://localhost:8000/panel/](http://localhost:8000/panel/)
   - PWA водителя: [http://localhost:8000/app/](http://localhost:8000/app/)

---

## 🏗 Дизайн-система Obsidian
Проект полностью переведен на дизайн-систему Obsidian, которая фокусируется на:
- **Глубокий темный режим** (`#09090b`) для работы диспетчеров в ночные смены.
- **Эффект стекла (Glassmorphism)** для навигационных элементов.
- **Акценты:** Яркий синий (`#3b82f6`) и контрастные индикаторы статусов.
- **Шрифты:** Premium Outfit & JetBrains Mono.

---

© 2026 Golden Bridge Logistics. Все права защищены.
