import json
import random
import secrets
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Dict, Optional

import bcrypt
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

app = FastAPI(title="MainBill")
app.add_middleware(SessionMiddleware, secret_key=secrets.token_hex(32))
templates = Jinja2Templates(directory="templates")


# DB helpers

def load_db() -> Dict[str, Any]:
    try:
        with open("db.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "users": [],
            "services": [],
            "tickets": [],
            "ticket_messages": [],
            "cdn_requests": [],
            "transactions": [],
        }


def save_db(db: Dict[str, Any]) -> None:
    with open("db.json", "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_config() -> Dict[str, Any]:
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)


# Auth helpers


def get_current_user(request: Request) -> Dict[str, Any]:
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/login"})

    db = load_db()
    user = next((u for u in db["users"] if u["id"] == user_id), None)
    if not user:
        request.session.clear()
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/login"})
    return user


def require_admin(user: Dict[str, Any]) -> Dict[str, Any]:
    if not user.get("is_admin"):
        raise HTTPException(status_code=status.HTTP_302_FOUND, headers={"Location": "/"})
    return user


def get_admin_user(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    return require_admin(user)


# Name generator

ADJ = [
    "azure",
    "crimson",
    "stellar",
    "golden",
    "silver",
    "cosmic",
    "mystic",
    "noble",
    "prime",
    "royal",
    "swift",
    "vivid",
    "quantum",
    "bright",
    "radiant",
]
NOUN = [
    "falcon",
    "phoenix",
    "dragon",
    "tiger",
    "eagle",
    "raven",
    "wolf",
    "bear",
    "lion",
    "hawk",
    "leopard",
    "panther",
    "jaguar",
    "lynx",
    "cobra",
]


def gen_name() -> str:
    return f"{random.choice(ADJ)}-{random.choice(NOUN)}"


# Pages


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    try:
        user = get_current_user(request)
    except HTTPException as exc:
        return RedirectResponse(url=exc.headers.get("Location", "/login"))
    return templates.TemplateResponse(
        "dashboard.html", {"request": request, "user": user, "is_admin": user.get("is_admin", False)}
    )


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "login"})


@app.post("/login")
async def login(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    db = load_db()
    user = next((u for u in db["users"] if u["username"] == username), None)
    if user and bcrypt.checkpw(password.encode(), user["password"].encode()):
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        request.session["is_admin"] = user.get("is_admin", False)
        target = "/admin" if user.get("is_admin") else "/"
        return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        "login.html",
        {"request": request, "mode": "login", "error": "Неверные данные"},
        status_code=status.HTTP_401_UNAUTHORIZED,
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "mode": "register"})


@app.post("/register")
async def register(request: Request):
    form = await request.form()
    username = form.get("username", "")
    password = form.get("password", "")

    db = load_db()
    if any(u["username"] == username for u in db["users"]):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "mode": "register", "error": "Пользователь существует"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user_id = max([u["id"] for u in db["users"]], default=0) + 1
    db["users"].append(
        {
            "id": user_id,
            "username": username,
            "password": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            "is_admin": False,
            "balance": 50.0,
        }
    )
    save_db(db)
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    try:
        user = get_current_user(request)
        require_admin(user)
    except HTTPException as exc:
        return RedirectResponse(url=exc.headers.get("Location", "/login"))
    return templates.TemplateResponse("admin.html", {"request": request, "user": user})


# API endpoints


@app.get("/api/config")
async def api_config(user: Dict[str, Any] = Depends(get_current_user)):
    return JSONResponse(load_config())


@app.api_route("/api/services", methods=["GET", "POST"])
async def api_services(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()

    if request.method == "GET":
        services = [s for s in db["services"] if s["owner_id"] == user["id"]]
        for svc in services:
            if svc.get("expires_at"):
                days_left = (datetime.fromisoformat(svc["expires_at"]) - datetime.now()).days
                if days_left <= 0:
                    svc["status"] = "expired"
                elif days_left <= 3:
                    svc["status"] = "expiring_soon"
        save_db(db)
        return JSONResponse(services)

    data = await request.json()

    balance_holder = next((u for u in db["users"] if u["id"] == user["id"]), None)
    if not balance_holder:
        return JSONResponse({"error": "User not found"}, status_code=status.HTTP_404_NOT_FOUND)

    price_str = data.get("price", "€0")
    price = float("".join(c for c in price_str if c.isdigit() or c == "."))

    if balance_holder.get("balance", 0) < price:
        return JSONResponse({"error": "Insufficient balance"}, status_code=status.HTTP_400_BAD_REQUEST)

    balance_holder["balance"] = balance_holder.get("balance", 0) - price

    trans_id = max([t["id"] for t in db.get("transactions", [])], default=0) + 1
    db.setdefault("transactions", []).append(
        {
            "id": trans_id,
            "user_id": user["id"],
            "amount": -price,
            "description": f"Order {data.get('service_type', 'Service')}",
            "created_at": datetime.now().isoformat(),
        }
    )

    service_id = max([s["id"] for s in db["services"]], default=0) + 1
    service = {
        "id": service_id,
        "name": gen_name(),
        "owner_id": user["id"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        **data,
    }
    db["services"].append(service)
    save_db(db)
    return JSONResponse({"id": service_id, "success": True})


@app.api_route("/api/services/{sid}", methods=["GET", "DELETE"])
async def api_service(sid: int, request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    service = next((s for s in db["services"] if s["id"] == sid and s["owner_id"] == user["id"]), None)

    if not service:
        return JSONResponse({"error": "Not found"}, status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "DELETE":
        db["services"] = [s for s in db["services"] if s["id"] != sid]
        save_db(db)
        return JSONResponse({"success": True})

    return JSONResponse(service)


@app.post("/api/services/{sid}/rename")
async def api_rename(sid: int, request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    service = next((s for s in db["services"] if s["id"] == sid and s["owner_id"] == user["id"]), None)
    if service:
        data = await request.json()
        service["name"] = data.get("new_name", service["name"])
        save_db(db)
    return JSONResponse({"success": True})


@app.post("/api/services/{sid}/request-renewal")
async def api_request_renewal(sid: int, user: Dict[str, Any] = Depends(get_current_user)):
    return JSONResponse({"success": True, "message": "Запрос отправлен"})


@app.api_route("/api/tickets", methods=["GET", "POST"])
async def api_tickets(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()

    if request.method == "GET":
        tickets = [t for t in db["tickets"] if t["user_id"] == user["id"]]
        enriched = []
        for ticket in tickets:
            messages = [m for m in db["ticket_messages"] if m["ticket_id"] == ticket["id"]]
            last_message = messages[-1]["message"] if messages else ""
            enriched.append({**ticket, "last_message": last_message})
        return JSONResponse(enriched)

    data = await request.json()
    tid = max([t["id"] for t in db["tickets"]], default=0) + 1
    ticket = {
        "id": tid,
        "user_id": user["id"],
        "subject": data["subject"],
        "priority": data.get("priority", "medium"),
        "status": "open",
        "created_at": datetime.now().isoformat(),
    }
    db["tickets"].append(ticket)

    mid = max([m["id"] for m in db["ticket_messages"]], default=0) + 1
    msg = {
        "id": mid,
        "ticket_id": tid,
        "sender": request.session.get("username", "user"),
        "message": data.get("message", ""),
        "created_at": datetime.now().isoformat(),
    }
    db["ticket_messages"].append(msg)

    save_db(db)
    return JSONResponse({"id": tid, "success": True})


@app.api_route("/api/tickets/{tid}/messages", methods=["GET", "POST"])
async def api_ticket_messages(tid: int, request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    ticket = next((t for t in db["tickets"] if t["id"] == tid and t["user_id"] == user["id"]), None)

    if not ticket:
        return JSONResponse({"error": "Not found"}, status_code=status.HTTP_404_NOT_FOUND)

    if request.method == "POST":
        data = await request.json()
        mid = max([m["id"] for m in db["ticket_messages"]], default=0) + 1
        msg = {
            "id": mid,
            "ticket_id": tid,
            "sender": request.session.get("username", "user"),
            "message": data.get("message", ""),
            "created_at": datetime.now().isoformat(),
        }
        db["ticket_messages"].append(msg)
        save_db(db)
        return JSONResponse({"success": True})

    messages = [m for m in db["ticket_messages"] if m["ticket_id"] == tid]
    return JSONResponse(messages)


@app.get("/api/balance")
async def api_balance(user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    holder = next((u for u in db["users"] if u["id"] == user["id"]), None)
    return JSONResponse({"balance": holder.get("balance", 0) if holder else 0})


@app.post("/api/balance/add")
async def api_balance_add(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    holder = next((u for u in db["users"] if u["id"] == user["id"]), None)
    if holder:
        data = await request.json()
        amount = float(data.get("amount", 0))
        holder["balance"] = holder.get("balance", 0) + amount
        save_db(db)
    return JSONResponse({"success": True})


@app.post("/api/cdn-request")
async def api_cdn_request(request: Request, user: Dict[str, Any] = Depends(get_current_user)):
    db = load_db()
    data = await request.json()
    rid = max([r["id"] for r in db["cdn_requests"]], default=0) + 1
    req = {
        "id": rid,
        "user_id": user["id"],
        "status": "pending",
        "created_at": datetime.now().isoformat(),
        **data,
    }
    db["cdn_requests"].append(req)
    save_db(db)
    return JSONResponse({"success": True})


# Admin API


@app.get("/api/admin/services")
async def api_admin_services(user: Dict[str, Any] = Depends(get_admin_user)):
    db = load_db()
    services = db["services"]
    for s in services:
        owner = next((u for u in db["users"] if u["id"] == s["owner_id"]), None)
        s["owner_username"] = owner["username"] if owner else "Unknown"
    return JSONResponse(services)


@app.post("/api/admin/services/{sid}/activate")
async def api_admin_activate(sid: int, request: Request, user: Dict[str, Any] = Depends(get_admin_user)):
    db = load_db()
    service = next((s for s in db["services"] if s["id"] == sid), None)
    if service:
        data = await request.json()
        service.update(data)
        service["status"] = "active"
        service["expires_at"] = (datetime.now() + timedelta(days=30)).isoformat()
        save_db(db)
    return JSONResponse({"success": True})


@app.post("/api/admin/services/{sid}/renew")
async def api_admin_renew(sid: int, user: Dict[str, Any] = Depends(get_admin_user)):
    db = load_db()
    service = next((s for s in db["services"] if s["id"] == sid), None)
    if service:
        service["status"] = "active"
        service["expires_at"] = (datetime.now() + timedelta(days=30)).isoformat()
        save_db(db)
    return JSONResponse({"success": True})


@app.get("/api/admin/tickets")
async def api_admin_tickets(user: Dict[str, Any] = Depends(get_admin_user)):
    db = load_db()
    tickets = db["tickets"]
    enriched = []
    for t in tickets:
        owner = next((u for u in db["users"] if u["id"] == t["user_id"]), None)
        messages = [m for m in db["ticket_messages"] if m["ticket_id"] == t["id"]]
        last_message = messages[-1]["message"] if messages else ""
        enriched.append({**t, "username": owner["username"] if owner else "Unknown", "last_message": last_message})
    return JSONResponse(enriched)


@app.api_route("/api/admin/tickets/{tid}/messages", methods=["GET", "POST"])
async def api_admin_ticket_messages(
    tid: int, request: Request, user: Dict[str, Any] = Depends(get_admin_user)
):
    db = load_db()

    if request.method == "POST":
        data = await request.json()
        mid = max([m["id"] for m in db["ticket_messages"]], default=0) + 1
        msg = {
            "id": mid,
            "ticket_id": tid,
            "sender": "admin",
            "message": data.get("message", ""),
            "created_at": datetime.now().isoformat(),
        }
        db["ticket_messages"].append(msg)
        save_db(db)
        return JSONResponse({"success": True})

    messages = [m for m in db["ticket_messages"] if m["ticket_id"] == tid]
    return JSONResponse(messages)


@app.get("/api/admin/cdn-requests")
async def api_admin_cdn(user: Dict[str, Any] = Depends(get_admin_user)):
    return JSONResponse(load_db()["cdn_requests"])


@app.post("/api/admin/cdn-requests/{rid}/activate")
async def api_admin_cdn_activate(
    rid: int, user: Dict[str, Any] = Depends(get_admin_user)
):
    db = load_db()
    cdn_req = next((r for r in db["cdn_requests"] if r["id"] == rid), None)
    if cdn_req:
        cdn_req["status"] = "active"

        tid = max([t["id"] for t in db["tickets"]], default=0) + 1
        ticket = {
            "id": tid,
            "user_id": cdn_req["user_id"],
            "subject": f"CDN активирован: {cdn_req['website_url']}",
            "priority": "high",
            "status": "open",
            "created_at": datetime.now().isoformat(),
        }
        db["tickets"].append(ticket)

        mid = max([m["id"] for m in db["ticket_messages"]], default=0) + 1
        msg = {
            "id": mid,
            "ticket_id": tid,
            "sender": "admin",
            "message": (
                "Здравствуйте! Ваш CDN запрос одобрен.\n\n"
                f"Детали:\n• Сайт: {cdn_req['website_url']}\n"
                f"• Трафик: {cdn_req['monthly_traffic']}\n"
                f"• Скорость: {cdn_req['required_speed']}\n\n"
                "Свяжемся для настройки."
            ),
            "created_at": datetime.now().isoformat(),
        }
        db["ticket_messages"].append(msg)

        save_db(db)
    return JSONResponse({"success": True})


# Init DB

def init_db() -> None:
    db = load_db()
    if not db["users"]:
        db["users"].append(
            {
                "id": 1,
                "username": "admin",
                "password": bcrypt.hashpw("admin".encode(), bcrypt.gensalt()).decode(),
                "is_admin": True,
                "balance": 999999.0,
            }
        )
        db["users"].append(
            {
                "id": 2,
                "username": "testuser",
                "password": bcrypt.hashpw("testpassword".encode(), bcrypt.gensalt()).decode(),
                "is_admin": False,
                "balance": 50.0,
            }
        )
        save_db(db)
        print("✓ DB initialized: admin/admin, testuser/testpassword")


if __name__ == "__main__":
    import uvicorn

    init_db()
    uvicorn.run(app, host="0.0.0.0", port=8000)
