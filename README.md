# Cloud Hosting Pro - Billing System v2.0

Современная биллинг-система для хостинг-провайдера на FastAPI с улучшенным интерфейсом и функционалом.

## Основные улучшения

### Backend (FastAPI)
- ✅ Полностью переписан на **FastAPI** (вместо Flask)
- ✅ Разделение на модули: `models.py`, `database.py`, `app.py`
- ✅ Pydantic модели для валидации
- ✅ WebSocket поддержка для live chat
- ✅ Улучшенная система уведомлений
- ✅ История транзакций
- ✅ Расширенная система тикетов (категории, приоритеты, статусы)

### Frontend
- ✅ Современный дизайн с glassmorphism эффектами
- ✅ Анимации и переходы
- ✅ Адаптивный интерфейс
- ✅ Toast уведомления
- ✅ Live chat интерфейс (с WebSocket)
- ✅ Улучшенная навигация
- ✅ Красивые статусные бейджи

### Новый функционал
- ✅ Система уведомлений в реальном времени
- ✅ История всех транзакций
- ✅ Расширенные тикеты с категориями и приоритетами
- ✅ Live chat с техподдержкой (WebSocket)
- ✅ Улучшенная админ-панель

## Установка

```bash
# Установить зависимости
pip install -r requirements.txt

# Запустить приложение
python app.py
# или
uvicorn app:app --host 0.0.0.0 --port 8000
```

## Доступ

- **URL**: http://localhost:8000
- **Админ**: admin / admin
- **Тестовый юзер**: testuser / testpassword

## Структура файлов

```
mainbill/
├── app.py                 # Главное FastAPI приложение
├── models.py              # Pydantic модели
├── database.py            # Функции работы с БД
├── config.json            # Конфигурация (тарифы, опции)
├── db.json                # База данных (JSON)
├── requirements.txt       # Зависимости
├── templates/
│   ├── base.html          # Базовый шаблон с стилями
│   ├── dashboard.html     # Пользовательский дашборд
│   ├── admin.html         # Админ-панель
│   └── login.html         # Страница входа/регистрации
└── main_flask_old.py      # Старая версия (Flask, бэкап)
```

## Основные возможности

### Для пользователей
- Заказ VPS, Dedicated серверов, VPN, VDesktop, S3
- Управление услугами (просмотр, переименование, удаление)
- Пополнение баланса
- Создание и управление тикетами с категориями и приоритетами
- Live chat с техподдержкой
- История транзакций
- Система уведомлений

### Для администраторов
- Активация услуг
- Продление услуг
- Управление тикетами
- Обработка CDN запросов
- Общение с пользователями через тикеты

## API Endpoints

### Аутентификация
- `GET /` - Главная страница (редирект на /login если не авторизован)
- `GET/POST /login` - Вход
- `GET/POST /register` - Регистрация
- `GET /logout` - Выход

### Пользовательские
- `GET /api/config` - Конфигурация (тарифы)
- `GET /api/balance` - Баланс
- `POST /api/balance/add` - Пополнить баланс
- `GET /api/transactions` - История транзакций
- `GET /api/notifications` - Уведомления
- `GET /api/services` - Список услуг
- `POST /api/services` - Создать услугу
- `GET /api/tickets` - Список тикетов
- `POST /api/tickets` - Создать тикет

### Админские
- `GET /api/admin/services` - Все услуги
- `POST /api/admin/services/{id}/activate` - Активировать услугу
- `POST /api/admin/services/{id}/renew` - Продлить услугу
- `GET /api/admin/tickets` - Все тикеты
- `GET /api/admin/cdn-requests` - CDN запросы

### WebSocket
- `/ws/chat` - Live chat для пользователей
- `/ws/admin/chat` - Live chat для админов

## Технологии

- **Backend**: FastAPI, Uvicorn, Pydantic
- **Frontend**: Bootstrap 5, Font Awesome, Vanilla JS
- **Database**: JSON (простой файловый storage)
- **Auth**: bcrypt, Sessions
- **Real-time**: WebSocket

## Разработка

Система разработана с упором на:
- **Качество кода**: Чистая архитектура, разделение на модули
- **UX/UI**: Современный дизайн, приятные анимации
- **Функциональность**: Все необходимое для биллинга
- **Простота**: Легко развертывать и поддерживать

## Будущие улучшения

- Полная реализация WebSocket live chat
- Добавление платежных систем (Stripe, PayPal)
- Email уведомления
- 2FA аутентификация
- API документация (Swagger/OpenAPI)
- Миграция на PostgreSQL
- Docker контейнеризация

---

**Version**: 2.0
**Framework**: FastAPI
**License**: MIT
