from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
import bcrypt
import secrets
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import asyncio

from models import *
from database import *

app = FastAPI(title="Cloud Hosting Billing", version="2.0")
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))

templates = Jinja2Templates(directory="templates")


# WebSocket connection manager for live chat
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, WebSocket] = {}
        self.admin_connections: list[WebSocket] = []

    async def connect_user(self, user_id: int, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[user_id] = websocket

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.append(websocket)

    def disconnect_user(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]

    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)

    async def send_to_user(self, user_id: int, message: dict):
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
            except:
                self.disconnect_user(user_id)

    async def send_to_admins(self, message: dict):
        dead_connections = []
        for connection in self.admin_connections:
            try:
                await connection.send_json(message)
            except:
                dead_connections.append(connection)
        for conn in dead_connections:
            self.disconnect_admin(conn)


manager = ConnectionManager()


# Helper functions
def gen_name():
    """Generate random service name"""
    adj = ['azure', 'crimson', 'stellar', 'golden', 'silver', 'cosmic', 'mystic', 'noble', 'prime', 'royal']
    noun = ['falcon', 'phoenix', 'dragon', 'tiger', 'eagle', 'raven', 'wolf', 'bear', 'lion', 'hawk']
    return f"{random.choice(adj)}-{random.choice(noun)}"


def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Get current user from session"""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    db = load_db()
    return get_user_by_id(db, user_id)


def require_auth(request: Request) -> Dict[str, Any]:
    """Require authentication"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


def require_admin(request: Request) -> Dict[str, Any]:
    """Require admin authentication"""
    user = require_auth(request)
    if not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# Initialize database with default users
def init_db():
    """Initialize database with default data"""
    db = load_db()
    if not db['users']:
        admin_hash = bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()).decode()
        test_hash = bcrypt.hashpw('testpassword'.encode(), bcrypt.gensalt()).decode()

        db['users'].append({
            'id': 1,
            'username': 'admin',
            'password': admin_hash,
            'is_admin': True,
            'balance': 999999.0
        })
        db['users'].append({
            'id': 2,
            'username': 'testuser',
            'password': test_hash,
            'is_admin': False,
            'balance': 50.0
        })
        save_db(db)
        print('✓ Database initialized: admin/admin, testuser/testpassword')


# Routes - Authentication
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get('username')
    password = form.get('password')

    db = load_db()
    user = get_user_by_username(db, username)

    if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
        request.session['user_id'] = user['id']
        request.session['username'] = user['username']
        request.session['is_admin'] = user.get('is_admin', False)

        if user.get('is_admin'):
            return RedirectResponse(url="/admin", status_code=302)
        return RedirectResponse(url="/", status_code=302)

    return templates.TemplateResponse("login.html", {
        "request": request,
        "error": "Неверные данные"
    })


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "register"})


@app.post("/register")
async def register(request: Request):
    form = await request.form()
    username = form.get('username')
    password = form.get('password')

    db = load_db()

    if get_user_by_username(db, username):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "mode": "register",
            "error": "Пользователь существует"
        })

    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    create_user(db, username, password_hash)
    save_db(db)

    return RedirectResponse(url="/login", status_code=302)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=302)


@app.get("/admin", response_class=HTMLResponse)
async def admin_page(request: Request):
    user = require_admin(request)
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})


# API Routes - Config
@app.get("/api/config")
async def api_config(request: Request):
    require_auth(request)
    return load_config()


# API Routes - User
@app.get("/api/balance")
async def api_balance(request: Request):
    user = require_auth(request)
    return {"balance": user.get('balance', 0)}


@app.post("/api/balance/add")
async def api_balance_add(request: Request, data: BalanceAdd):
    user = require_auth(request)
    db = load_db()

    db_user = get_user_by_id(db, user['id'])
    if db_user:
        db_user['balance'] = db_user.get('balance', 0) + data.amount

        # Create transaction
        create_transaction(db, {
            'user_id': user['id'],
            'amount': data.amount,
            'description': f"Пополнение баланса",
            'created_at': datetime.now().isoformat(),
            'type': 'credit'
        })

        # Create notification
        create_notification(db, {
            'user_id': user['id'],
            'type': 'success',
            'title': 'Баланс пополнен',
            'message': f'Ваш баланс пополнен на €{data.amount:.2f}',
            'created_at': datetime.now().isoformat()
        })

        save_db(db)

    return {"success": True, "balance": db_user.get('balance', 0)}


@app.get("/api/transactions")
async def api_transactions(request: Request):
    user = require_auth(request)
    db = load_db()
    return get_user_transactions(db, user['id'])


@app.get("/api/notifications")
async def api_notifications(request: Request, unread_only: bool = False):
    user = require_auth(request)
    db = load_db()
    return get_user_notifications(db, user['id'], unread_only)


@app.post("/api/notifications/{notif_id}/read")
async def api_notification_read(request: Request, notif_id: int):
    user = require_auth(request)
    db = load_db()
    mark_notification_read(db, notif_id, user['id'])
    save_db(db)
    return {"success": True}


# API Routes - Services
@app.get("/api/services")
async def api_services(request: Request):
    user = require_auth(request)
    db = load_db()
    services = get_user_services(db, user['id'])

    # Update expiration status
    for s in services:
        if s.get('expires_at'):
            try:
                expires = datetime.fromisoformat(s['expires_at'])
                days_left = (expires - datetime.now()).days
                if days_left <= 0:
                    s['status'] = 'expired'
                elif days_left <= 3:
                    s['status'] = 'expiring_soon'
            except:
                pass

    save_db(db)
    return services


@app.post("/api/services")
async def api_create_service(request: Request, service: ServiceCreate):
    user = require_auth(request)
    db = load_db()

    # Parse price
    price_str = service.price
    price = float(''.join(c for c in price_str if c.isdigit() or c == '.'))

    # Check balance
    db_user = get_user_by_id(db, user['id'])
    if db_user.get('balance', 0) < price:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # Deduct balance
    db_user['balance'] = db_user.get('balance', 0) - price

    # Create transaction
    create_transaction(db, {
        'user_id': user['id'],
        'amount': -price,
        'description': f"Заказ {service.service_type}",
        'created_at': datetime.now().isoformat(),
        'type': 'debit'
    })

    # Create service
    service_data = service.dict()
    service_data.update({
        'name': gen_name(),
        'owner_id': user['id'],
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    })

    new_service = create_service(db, service_data)

    # Create notification
    create_notification(db, {
        'user_id': user['id'],
        'type': 'info',
        'title': 'Услуга заказана',
        'message': f'{service.service_type} "{new_service["name"]}" в обработке',
        'created_at': datetime.now().isoformat(),
        'link': f'/services/{new_service["id"]}'
    })

    save_db(db)
    return {"id": new_service['id'], "success": True}


@app.get("/api/services/{service_id}")
async def api_get_service(request: Request, service_id: int):
    user = require_auth(request)
    db = load_db()
    service = get_service_by_id(db, service_id, user['id'])

    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    return service


@app.delete("/api/services/{service_id}")
async def api_delete_service(request: Request, service_id: int):
    user = require_auth(request)
    db = load_db()

    service = get_service_by_id(db, service_id, user['id'])
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")

    delete_service(db, service_id)
    save_db(db)
    return {"success": True}


@app.post("/api/services/{service_id}/rename")
async def api_rename_service(request: Request, service_id: int):
    user = require_auth(request)
    data = await request.json()
    db = load_db()

    service = get_service_by_id(db, service_id, user['id'])
    if service:
        service['name'] = data['new_name']
        save_db(db)

    return {"success": True}


# API Routes - Tickets
@app.get("/api/tickets")
async def api_tickets(request: Request):
    user = require_auth(request)
    db = load_db()
    return get_user_tickets(db, user['id'])


@app.post("/api/tickets")
async def api_create_ticket(request: Request, ticket: TicketCreate):
    user = require_auth(request)
    db = load_db()

    # Create ticket
    new_ticket = create_ticket(db, {
        'user_id': user['id'],
        'subject': ticket.subject,
        'priority': ticket.priority,
        'category': ticket.category,
        'status': 'open',
        'created_at': datetime.now().isoformat()
    })

    # Create first message
    create_ticket_message(db, {
        'ticket_id': new_ticket['id'],
        'sender': user['username'],
        'sender_type': 'user',
        'message': ticket.message,
        'created_at': datetime.now().isoformat()
    })

    # Create notification
    create_notification(db, {
        'user_id': user['id'],
        'type': 'info',
        'title': 'Тикет создан',
        'message': f'Тикет #{new_ticket["id"]}: {ticket.subject}',
        'created_at': datetime.now().isoformat()
    })

    save_db(db)
    return {"id": new_ticket['id'], "success": True}


@app.get("/api/tickets/{ticket_id}/messages")
async def api_ticket_messages(request: Request, ticket_id: int):
    user = require_auth(request)
    db = load_db()

    ticket = get_ticket_by_id(db, ticket_id, user['id'])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return get_ticket_messages(db, ticket_id)


@app.post("/api/tickets/{ticket_id}/messages")
async def api_create_ticket_message(request: Request, ticket_id: int, message: MessageCreate):
    user = require_auth(request)
    db = load_db()

    ticket = get_ticket_by_id(db, ticket_id, user['id'])
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update ticket status and timestamp
    ticket['status'] = 'waiting'
    ticket['updated_at'] = datetime.now().isoformat()

    create_ticket_message(db, {
        'ticket_id': ticket_id,
        'sender': user['username'],
        'sender_type': 'user',
        'message': message.message,
        'created_at': datetime.now().isoformat()
    })

    save_db(db)
    return {"success": True}


# API Routes - CDN
@app.post("/api/cdn-request")
async def api_cdn_request(request: Request, cdn: CDNRequestCreate):
    user = require_auth(request)
    db = load_db()

    cdn_data = cdn.dict()
    cdn_data.update({
        'user_id': user['id'],
        'status': 'pending',
        'created_at': datetime.now().isoformat()
    })

    create_cdn_request(db, cdn_data)
    save_db(db)

    return {"success": True}


# WebSocket for live chat
@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        # Get user info from query params or initial message
        init_data = await websocket.receive_json()
        user_id = init_data.get('user_id')

        if not user_id:
            await websocket.close(code=1008)
            return

        db = load_db()
        user = get_user_by_id(db, user_id)

        if not user:
            await websocket.close(code=1008)
            return

        # Connect user
        await manager.connect_user(user_id, websocket)

        # Get or create chat
        chat = get_user_chat(db, user_id, create_if_missing=True)
        save_db(db)

        # Send chat history
        messages = get_chat_messages(db, chat['id'])
        await websocket.send_json({
            'type': 'history',
            'messages': messages
        })

        # Notify admins
        await manager.send_to_admins({
            'type': 'user_connected',
            'user_id': user_id,
            'username': user['username']
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            if data.get('type') == 'message':
                db = load_db()

                # Create message
                msg = create_chat_message(db, {
                    'chat_id': chat['id'],
                    'sender': user['username'],
                    'sender_type': 'user',
                    'message': data.get('message'),
                    'created_at': datetime.now().isoformat()
                })

                save_db(db)

                # Send to user (confirmation)
                await manager.send_to_user(user_id, {
                    'type': 'message',
                    'message': msg
                })

                # Send to admins
                await manager.send_to_admins({
                    'type': 'user_message',
                    'user_id': user_id,
                    'username': user['username'],
                    'message': msg
                })

    except WebSocketDisconnect:
        manager.disconnect_user(user_id)
        await manager.send_to_admins({
            'type': 'user_disconnected',
            'user_id': user_id
        })


@app.websocket("/ws/admin/chat")
async def websocket_admin_chat(websocket: WebSocket):
    await websocket.accept()

    try:
        # Verify admin (in production, use proper auth)
        init_data = await websocket.receive_json()
        user_id = init_data.get('user_id')

        db = load_db()
        user = get_user_by_id(db, user_id)

        if not user or not user.get('is_admin'):
            await websocket.close(code=1008)
            return

        # Connect admin
        await manager.connect_admin(websocket)

        # Send active chats
        active_chats = [c for c in db['chats'] if c['status'] == 'active']
        await websocket.send_json({
            'type': 'active_chats',
            'chats': active_chats
        })

        # Listen for messages
        while True:
            data = await websocket.receive_json()

            if data.get('type') == 'message':
                target_user_id = data.get('user_id')
                message_text = data.get('message')

                db = load_db()
                chat = get_user_chat(db, target_user_id)

                if chat:
                    # Create message
                    msg = create_chat_message(db, {
                        'chat_id': chat['id'],
                        'sender': 'admin',
                        'sender_type': 'admin',
                        'message': message_text,
                        'created_at': datetime.now().isoformat()
                    })

                    save_db(db)

                    # Send to user
                    await manager.send_to_user(target_user_id, {
                        'type': 'message',
                        'message': msg
                    })

                    # Confirm to admin
                    await websocket.send_json({
                        'type': 'message_sent',
                        'message': msg
                    })

    except WebSocketDisconnect:
        manager.disconnect_admin(websocket)


# Admin API Routes
@app.get("/api/admin/services")
async def api_admin_services(request: Request):
    require_admin(request)
    db = load_db()
    services = db['services']

    # Add owner username
    for s in services:
        user = get_user_by_id(db, s['owner_id'])
        s['owner_username'] = user['username'] if user else 'Unknown'

    return services


@app.post("/api/admin/services/{service_id}/activate")
async def api_admin_activate(request: Request, service_id: int, activation: ServiceActivation):
    require_admin(request)
    db = load_db()

    service = get_service_by_id(db, service_id)
    if service:
        # Update service with activation data
        service.update(activation.dict(exclude_none=True))
        service['status'] = 'active'
        service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()

        # Create notification for user
        create_notification(db, {
            'user_id': service['owner_id'],
            'type': 'success',
            'title': 'Услуга активирована',
            'message': f'{service["service_type"]} "{service["name"]}" активирована',
            'created_at': datetime.now().isoformat()
        })

        save_db(db)

    return {"success": True}


@app.post("/api/admin/services/{service_id}/renew")
async def api_admin_renew(request: Request, service_id: int):
    require_admin(request)
    db = load_db()

    service = get_service_by_id(db, service_id)
    if service:
        service['status'] = 'active'
        service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()

        # Create notification
        create_notification(db, {
            'user_id': service['owner_id'],
            'type': 'success',
            'title': 'Услуга продлена',
            'message': f'{service["service_type"]} "{service["name"]}" продлена на 30 дней',
            'created_at': datetime.now().isoformat()
        })

        save_db(db)

    return {"success": True}


@app.get("/api/admin/tickets")
async def api_admin_tickets(request: Request):
    require_admin(request)
    db = load_db()
    tickets = db['tickets']

    # Add username
    for t in tickets:
        user = get_user_by_id(db, t['user_id'])
        t['username'] = user['username'] if user else 'Unknown'

    return tickets


@app.get("/api/admin/tickets/{ticket_id}/messages")
async def api_admin_ticket_messages(request: Request, ticket_id: int):
    require_admin(request)
    db = load_db()
    return get_ticket_messages(db, ticket_id)


@app.post("/api/admin/tickets/{ticket_id}/messages")
async def api_admin_create_ticket_message(request: Request, ticket_id: int, message: MessageCreate):
    require_admin(request)
    db = load_db()

    ticket = get_ticket_by_id(db, ticket_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update ticket
    ticket['status'] = 'in_progress'
    ticket['updated_at'] = datetime.now().isoformat()

    create_ticket_message(db, {
        'ticket_id': ticket_id,
        'sender': 'admin',
        'sender_type': 'admin',
        'message': message.message,
        'created_at': datetime.now().isoformat()
    })

    # Create notification for user
    create_notification(db, {
        'user_id': ticket['user_id'],
        'type': 'info',
        'title': 'Новый ответ в тикете',
        'message': f'Администратор ответил в тикете #{ticket_id}',
        'created_at': datetime.now().isoformat()
    })

    save_db(db)
    return {"success": True}


@app.get("/api/admin/cdn-requests")
async def api_admin_cdn(request: Request):
    require_admin(request)
    db = load_db()
    return db['cdn_requests']


@app.post("/api/admin/cdn-requests/{cdn_id}/activate")
async def api_admin_cdn_activate(request: Request, cdn_id: int):
    require_admin(request)
    db = load_db()

    cdn_req = get_cdn_request_by_id(db, cdn_id)
    if cdn_req:
        cdn_req['status'] = 'active'

        # Create ticket
        ticket = create_ticket(db, {
            'user_id': cdn_req['user_id'],
            'subject': f"CDN активирован: {cdn_req['website_url']}",
            'priority': 'high',
            'category': 'sales',
            'status': 'open',
            'created_at': datetime.now().isoformat()
        })

        # Create message
        create_ticket_message(db, {
            'ticket_id': ticket['id'],
            'sender': 'admin',
            'sender_type': 'admin',
            'message': f"""Здравствуйте!

Ваш CDN запрос одобрен.

Детали:
• Сайт: {cdn_req['website_url']}
• Трафик: {cdn_req['monthly_traffic']}
• Скорость: {cdn_req['required_speed']}

Мы свяжемся с вами для настройки.""",
            'created_at': datetime.now().isoformat()
        })

        # Create notification
        create_notification(db, {
            'user_id': cdn_req['user_id'],
            'type': 'success',
            'title': 'CDN запрос одобрен',
            'message': 'Ваш CDN запрос был одобрен. Проверьте тикеты.',
            'created_at': datetime.now().isoformat()
        })

        save_db(db)

    return {"success": True}


# Startup event
@app.on_event("startup")
async def startup_event():
    init_db()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
