from fastapi import FastAPI, HTTPException, Depends, status, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timedelta
import json
import bcrypt
import secrets
import random
from pathlib import Path
from functools import lru_cache
from typing import Optional

app = FastAPI(title="Cloud Billing Pro")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== MODELS ====================
class LoginRequest(BaseModel):
    username: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    balance: float
    is_admin: bool

class ServiceCreate(BaseModel):
    service_type: str
    plan: str
    cpu: str
    ram: str
    disk: str
    region: str
    os: str
    price: str
    setup_fee: str = "€0"
    datacenter: str = ""
    network: str = ""
    premium_support: bool = False

class TicketCreate(BaseModel):
    subject: str
    message: str
    priority: str = "medium"

class TicketMessageCreate(BaseModel):
    message: str

class BalanceTopUp(BaseModel):
    amount: float

# ==================== DB HELPERS ====================
DB_FILE = Path("db.json")
CONFIG_FILE = Path("config.json")

def load_db():
    try:
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {
            'users': [],
            'services': [],
            'tickets': [],
            'ticket_messages': [],
            'cdn_requests': [],
            'transactions': []
        }

def save_db(db):
    with open(DB_FILE, 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

# ==================== AUTH HELPERS ====================
class AuthManager:
    def __init__(self):
        self.sessions = {}

    def create_session(self, user_id: int, username: str, is_admin: bool) -> str:
        token = secrets.token_urlsafe(32)
        self.sessions[token] = {
            'user_id': user_id,
            'username': username,
            'is_admin': is_admin,
            'created_at': datetime.now()
        }
        return token

    def validate_session(self, token: str):
        return self.sessions.get(token)

auth_manager = AuthManager()

def get_current_user(token: Optional[str] = Query(None), authorization: Optional[str] = Header(None)):
    # Try to get token from query parameter, then from Authorization header
    auth_token = token
    if not auth_token and authorization:
        try:
            auth_token = authorization.split("Bearer ")[-1]
        except:
            pass

    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user_session = auth_manager.validate_session(auth_token)
    if not user_session:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user_session

# ==================== UTILITIES ====================
ADJ = ['azure', 'crimson', 'stellar', 'golden', 'silver', 'cosmic', 'mystic', 'noble', 'prime', 'royal']
NOUN = ['falcon', 'phoenix', 'dragon', 'tiger', 'eagle', 'raven', 'wolf', 'bear', 'lion', 'hawk']

def gen_service_name():
    return f"{random.choice(ADJ)}-{random.choice(NOUN)}"

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# ==================== AUTH ROUTES ====================
@app.post("/api/auth/login")
def login(req: LoginRequest):
    db = load_db()
    user = next((u for u in db['users'] if u['username'] == req.username), None)

    if not user or not verify_password(req.password, user['password']):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = auth_manager.create_session(user['id'], user['username'], user.get('is_admin', False))
    return {
        'token': token,
        'user': {
            'id': user['id'],
            'username': user['username'],
            'is_admin': user.get('is_admin', False),
            'balance': user.get('balance', 0)
        }
    }

@app.post("/api/auth/register")
def register(req: LoginRequest):
    db = load_db()

    if any(u['username'] == req.username for u in db['users']):
        raise HTTPException(status_code=400, detail="User exists")

    user_id = max([u['id'] for u in db['users']], default=0) + 1
    user = {
        'id': user_id,
        'username': req.username,
        'password': hash_password(req.password),
        'is_admin': False,
        'balance': 50.0,
        'created_at': datetime.now().isoformat()
    }
    db['users'].append(user)
    save_db(db)

    token = auth_manager.create_session(user_id, req.username, False)
    return {'token': token, 'user': {'id': user_id, 'username': req.username, 'is_admin': False, 'balance': 50.0}}

# ==================== USER ROUTES ====================
@app.get("/api/user")
def get_user(user_session = Depends(get_current_user)):
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == user_session['user_id']), None)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        'id': user['id'],
        'username': user['username'],
        'balance': user.get('balance', 0),
        'is_admin': user.get('is_admin', False)
    }

@app.get("/api/balance")
def get_balance(user_session = Depends(get_current_user)):
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == user_session['user_id']), None)
    if not user:
        raise HTTPException(status_code=404)
    return {'balance': user.get('balance', 0)}

@app.post("/api/balance/topup")
def topup_balance(req: BalanceTopUp, user_session = Depends(get_current_user)):
    if req.amount <= 0:
        raise HTTPException(status_code=400, detail="Invalid amount")

    db = load_db()
    user = next((u for u in db['users'] if u['id'] == user_session['user_id']), None)
    if not user:
        raise HTTPException(status_code=404)

    user['balance'] = user.get('balance', 0) + req.amount

    trans_id = max([t['id'] for t in db.get('transactions', [])], default=0) + 1
    db.setdefault('transactions', []).append({
        'id': trans_id,
        'user_id': user_session['user_id'],
        'amount': req.amount,
        'type': 'topup',
        'description': 'Balance top-up',
        'created_at': datetime.now().isoformat()
    })

    save_db(db)
    return {'success': True, 'balance': user['balance']}

# ==================== SERVICES ROUTES ====================
@app.get("/api/services")
def list_services(user_session = Depends(get_current_user)):
    db = load_db()
    services = [s for s in db['services'] if s['owner_id'] == user_session['user_id']]

    for s in services:
        if s.get('expires_at'):
            expires = datetime.fromisoformat(s['expires_at'])
            days_left = (expires - datetime.now()).days
            if days_left <= 0:
                s['status'] = 'expired'
                s['days_left'] = 0
            elif days_left <= 3:
                s['status'] = 'expiring_soon'
                s['days_left'] = days_left
            else:
                s['days_left'] = days_left

    save_db(db)
    return services

@app.post("/api/services")
def create_service(req: ServiceCreate, user_session = Depends(get_current_user)):
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == user_session['user_id']), None)
    if not user:
        raise HTTPException(status_code=404)

    price_str = req.price
    price = float(''.join(c for c in price_str if c.isdigit() or c == '.')) if price_str else 0

    if user.get('balance', 0) < price:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    user['balance'] = user.get('balance', 0) - price

    trans_id = max([t['id'] for t in db.get('transactions', [])], default=0) + 1
    db.setdefault('transactions', []).append({
        'id': trans_id,
        'user_id': user_session['user_id'],
        'amount': -price,
        'type': 'service_order',
        'description': f"Order {req.service_type}",
        'created_at': datetime.now().isoformat()
    })

    service_id = max([s['id'] for s in db['services']], default=0) + 1
    service = {
        'id': service_id,
        'name': gen_service_name(),
        'owner_id': user_session['user_id'],
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        'service_type': req.service_type,
        'plan': req.plan,
        'cpu': req.cpu,
        'ram': req.ram,
        'disk': req.disk,
        'region': req.region,
        'os': req.os,
        'price': req.price,
        'setup_fee': req.setup_fee,
        'datacenter': req.datacenter,
        'network': req.network,
        'premium_support': req.premium_support,
    }
    db['services'].append(service)
    save_db(db)

    return {'id': service_id, 'success': True, 'service': service}

@app.get("/api/services/{service_id}")
def get_service(service_id: int, user_session = Depends(get_current_user)):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == service_id and s['owner_id'] == user_session['user_id']), None)
    if not service:
        raise HTTPException(status_code=404)
    return service

@app.delete("/api/services/{service_id}")
def delete_service(service_id: int, user_session = Depends(get_current_user)):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == service_id and s['owner_id'] == user_session['user_id']), None)
    if not service:
        raise HTTPException(status_code=404)

    db['services'] = [s for s in db['services'] if s['id'] != service_id]
    save_db(db)
    return {'success': True}

@app.post("/api/services/{service_id}/rename")
def rename_service(service_id: int, data: dict, user_session = Depends(get_current_user)):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == service_id and s['owner_id'] == user_session['user_id']), None)
    if not service:
        raise HTTPException(status_code=404)

    service['name'] = data.get('new_name', service['name'])
    save_db(db)
    return {'success': True}

# ==================== TICKETS ROUTES ====================
@app.get("/api/tickets")
def list_tickets(user_session = Depends(get_current_user)):
    db = load_db()
    tickets = [t for t in db['tickets'] if t['user_id'] == user_session['user_id']]
    for t in tickets:
        messages = [m for m in db['ticket_messages'] if m['ticket_id'] == t['id']]
        t['message_count'] = len(messages)
        if messages:
            t['last_message'] = messages[-1]['created_at']
    return tickets

@app.post("/api/tickets")
def create_ticket(req: TicketCreate, user_session = Depends(get_current_user)):
    db = load_db()

    tid = max([t['id'] for t in db['tickets']], default=0) + 1
    ticket = {
        'id': tid,
        'user_id': user_session['user_id'],
        'subject': req.subject,
        'priority': req.priority,
        'status': 'open',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    db['tickets'].append(ticket)

    mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
    msg = {
        'id': mid,
        'ticket_id': tid,
        'sender': user_session['username'],
        'sender_id': user_session['user_id'],
        'message': req.message,
        'created_at': datetime.now().isoformat()
    }
    db['ticket_messages'].append(msg)

    save_db(db)
    return {'id': tid, 'success': True}

@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id: int, user_session = Depends(get_current_user)):
    db = load_db()
    ticket = next((t for t in db['tickets'] if t['id'] == ticket_id and t['user_id'] == user_session['user_id']), None)
    if not ticket:
        raise HTTPException(status_code=404)

    messages = [m for m in db['ticket_messages'] if m['ticket_id'] == ticket_id]
    return {'ticket': ticket, 'messages': messages}

@app.post("/api/tickets/{ticket_id}/messages")
def add_ticket_message(ticket_id: int, req: TicketMessageCreate, user_session = Depends(get_current_user)):
    db = load_db()
    ticket = next((t for t in db['tickets'] if t['id'] == ticket_id and t['user_id'] == user_session['user_id']), None)
    if not ticket:
        raise HTTPException(status_code=404)

    mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
    msg = {
        'id': mid,
        'ticket_id': ticket_id,
        'sender': user_session['username'],
        'sender_id': user_session['user_id'],
        'message': req.message,
        'created_at': datetime.now().isoformat()
    }
    db['ticket_messages'].append(msg)
    ticket['updated_at'] = datetime.now().isoformat()

    save_db(db)
    return {'success': True}

@app.post("/api/tickets/{ticket_id}/close")
def close_ticket(ticket_id: int, user_session = Depends(get_current_user)):
    db = load_db()
    ticket = next((t for t in db['tickets'] if t['id'] == ticket_id and t['user_id'] == user_session['user_id']), None)
    if not ticket:
        raise HTTPException(status_code=404)

    ticket['status'] = 'closed'
    save_db(db)
    return {'success': True}

# ==================== CONFIG ROUTES ====================
@app.get("/api/config")
def get_config():
    return load_config()

# ==================== ADMIN ROUTES ====================
def get_admin_user(user_session = Depends(get_current_user)):
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == user_session['user_id']), None)
    if not user or not user.get('is_admin'):
        raise HTTPException(status_code=403, detail="Not admin")
    return user_session

@app.get("/api/admin/services")
def admin_list_services(admin = Depends(get_admin_user)):
    db = load_db()
    for s in db['services']:
        user = next((u for u in db['users'] if u['id'] == s['owner_id']), None)
        s['owner_username'] = user['username'] if user else 'Unknown'
    return db['services']

@app.post("/api/admin/services/{service_id}/activate")
def admin_activate_service(service_id: int, data: dict, admin = Depends(get_admin_user)):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == service_id), None)
    if not service:
        raise HTTPException(status_code=404)

    service.update(data)
    service['status'] = 'active'
    service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
    save_db(db)

    return {'success': True}

@app.post("/api/admin/services/{service_id}/renew")
def admin_renew_service(service_id: int, admin = Depends(get_admin_user)):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == service_id), None)
    if not service:
        raise HTTPException(status_code=404)

    service['status'] = 'active'
    service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
    save_db(db)

    return {'success': True}

@app.get("/api/admin/tickets")
def admin_list_tickets(admin = Depends(get_admin_user)):
    db = load_db()
    for t in db['tickets']:
        user = next((u for u in db['users'] if u['id'] == t['user_id']), None)
        t['username'] = user['username'] if user else 'Unknown'
    return db['tickets']

@app.get("/api/admin/tickets/{ticket_id}/messages")
def admin_get_ticket_messages(ticket_id: int, admin = Depends(get_admin_user)):
    db = load_db()
    messages = [m for m in db['ticket_messages'] if m['ticket_id'] == ticket_id]
    return messages

@app.post("/api/admin/tickets/{ticket_id}/messages")
def admin_add_ticket_message(ticket_id: int, req: TicketMessageCreate, admin = Depends(get_admin_user)):
    db = load_db()

    mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
    msg = {
        'id': mid,
        'ticket_id': ticket_id,
        'sender': 'admin',
        'sender_id': admin['user_id'],
        'message': req.message,
        'created_at': datetime.now().isoformat()
    }
    db['ticket_messages'].append(msg)

    ticket = next((t for t in db['tickets'] if t['id'] == ticket_id), None)
    if ticket:
        ticket['updated_at'] = datetime.now().isoformat()

    save_db(db)
    return {'success': True}

@app.post("/api/admin/tickets/{ticket_id}/close")
def admin_close_ticket(ticket_id: int, admin = Depends(get_admin_user)):
    db = load_db()
    ticket = next((t for t in db['tickets'] if t['id'] == ticket_id), None)
    if not ticket:
        raise HTTPException(status_code=404)

    ticket['status'] = 'closed'
    save_db(db)
    return {'success': True}

# ==================== STATIC & PAGES ====================
@app.get("/")
def index():
    return FileResponse("templates/index.html")

@app.get("/login")
def login_page():
    return FileResponse("templates/login.html")

@app.get("/admin")
def admin_page():
    return FileResponse("templates/admin.html")

# Initialize DB
def init_db():
    db = load_db()
    if not db['users']:
        db['users'] = [
            {
                'id': 1,
                'username': 'admin',
                'password': hash_password('admin'),
                'is_admin': True,
                'balance': 999999.0,
                'created_at': datetime.now().isoformat()
            },
            {
                'id': 2,
                'username': 'testuser',
                'password': hash_password('testpassword'),
                'is_admin': False,
                'balance': 150.0,
                'created_at': datetime.now().isoformat()
            }
        ]
        save_db(db)
        print('✓ DB initialized: admin/admin, testuser/testpassword')

init_db()

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
