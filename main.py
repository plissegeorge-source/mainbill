from flask import Flask, render_template, request, redirect, session, jsonify
import json
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
import secrets
import random

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)


# DB helpers
def load_db():
    try:
        with open('db.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {'users': [], 'services': [], 'tickets': [], 'ticket_messages': [], 'cdn_requests': [],
                'transactions': []}


def save_db(db):
    with open('db.json', 'w', encoding='utf-8') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)


# Auth decorator
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)

    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        db = load_db()
        user = next((u for u in db['users'] if u['id'] == session['user_id']), None)
        if not user or not user.get('is_admin'):
            return redirect('/')
        return f(*args, **kwargs)

    return decorated


# Name generator
ADJ = ['azure', 'crimson', 'stellar', 'golden', 'silver', 'cosmic', 'mystic', 'noble', 'prime', 'royal', 'swift',
       'vivid', 'quantum', 'bright', 'radiant']
NOUN = ['falcon', 'phoenix', 'dragon', 'tiger', 'eagle', 'raven', 'wolf', 'bear', 'lion', 'hawk', 'leopard', 'panther',
        'jaguar', 'lynx', 'cobra']


def gen_name():
    return f"{random.choice(ADJ)}-{random.choice(NOUN)}"


# Routes
@app.route('/')
@login_required
def index():
    return render_template('dashboard.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        db = load_db()
        username = request.form['username']
        password = request.form['password']

        user = next((u for u in db['users'] if u['username'] == username), None)
        if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user.get('is_admin', False)
            return redirect('/admin' if user.get('is_admin') else '/')
        return render_template('login.html', error='Неверные данные')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        db = load_db()
        username = request.form['username']
        password = request.form['password']

        if any(u['username'] == username for u in db['users']):
            return render_template('login.html', error='Пользователь существует', mode='register')

        user_id = max([u['id'] for u in db['users']], default=0) + 1
        db['users'].append({
            'id': user_id,
            'username': username,
            'password': bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode(),
            'is_admin': False,
            'balance': 50.0
        })
        save_db(db)
        return redirect('/login')
    return render_template('login.html', mode='register')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


@app.route('/admin')
@admin_required
def admin():
    return render_template('admin.html')


# API
@app.route('/api/config')
@login_required
def api_config():
    return jsonify(load_config())


@app.route('/api/services', methods=['GET', 'POST'])
@login_required
def api_services():
    db = load_db()

    if request.method == 'GET':
        services = [s for s in db['services'] if s['owner_id'] == session['user_id']]
        for s in services:
            if s.get('expires_at'):
                days_left = (datetime.fromisoformat(s['expires_at']) - datetime.now()).days
                if days_left <= 0:
                    s['status'] = 'expired'
                elif days_left <= 3:
                    s['status'] = 'expiring_soon'
        save_db(db)
        return jsonify(services)

    data = request.json

    # Списание баланса
    user = next((u for u in db['users'] if u['id'] == session['user_id']), None)
    if not user:
        return jsonify({'error': 'User not found'}), 404

    price_str = data.get('price', '€0')
    price = float(''.join(c for c in price_str if c.isdigit() or c == '.'))

    if user.get('balance', 0) < price:
        return jsonify({'error': 'Insufficient balance'}), 400

    user['balance'] = user.get('balance', 0) - price

    # Транзакция
    trans_id = max([t['id'] for t in db.get('transactions', [])], default=0) + 1
    db.setdefault('transactions', []).append({
        'id': trans_id,
        'user_id': session['user_id'],
        'amount': -price,
        'description': f"Order {data.get('service_type', 'Service')}",
        'created_at': datetime.now().isoformat()
    })

    service_id = max([s['id'] for s in db['services']], default=0) + 1
    service = {
        'id': service_id,
        'name': gen_name(),
        'owner_id': session['user_id'],
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        **data
    }
    db['services'].append(service)
    save_db(db)
    return jsonify({'id': service_id, 'success': True})


@app.route('/api/services/<int:sid>', methods=['GET', 'DELETE'])
@login_required
def api_service(sid):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == sid and s['owner_id'] == session['user_id']), None)

    if not service:
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'DELETE':
        db['services'] = [s for s in db['services'] if s['id'] != sid]
        save_db(db)
        return jsonify({'success': True})

    return jsonify(service)


@app.route('/api/services/<int:sid>/rename', methods=['POST'])
@login_required
def api_rename(sid):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == sid and s['owner_id'] == session['user_id']), None)
    if service:
        service['name'] = request.json['new_name']
        save_db(db)
    return jsonify({'success': True})


@app.route('/api/services/<int:sid>/request-renewal', methods=['POST'])
@login_required
def api_request_renewal(sid):
    return jsonify({'success': True, 'message': 'Запрос отправлен'})


@app.route('/api/tickets', methods=['GET', 'POST'])
@login_required
def api_tickets():
    db = load_db()

    if request.method == 'GET':
        tickets = [t for t in db['tickets'] if t['user_id'] == session['user_id']]
        return jsonify(tickets)

    data = request.json
    tid = max([t['id'] for t in db['tickets']], default=0) + 1
    ticket = {
        'id': tid,
        'user_id': session['user_id'],
        'subject': data['subject'],
        'priority': data.get('priority', 'medium'),
        'status': 'open',
        'created_at': datetime.now().isoformat()
    }
    db['tickets'].append(ticket)

    # Первое сообщение
    mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
    msg = {
        'id': mid,
        'ticket_id': tid,
        'sender': session.get('username', 'user'),
        'message': data.get('message', ''),
        'created_at': datetime.now().isoformat()
    }
    db['ticket_messages'].append(msg)

    save_db(db)
    return jsonify({'id': tid, 'success': True})


@app.route('/api/tickets/<int:tid>/messages', methods=['GET', 'POST'])
@login_required
def api_ticket_messages(tid):
    db = load_db()
    ticket = next((t for t in db['tickets'] if t['id'] == tid and t['user_id'] == session['user_id']), None)

    if not ticket:
        return jsonify({'error': 'Not found'}), 404

    if request.method == 'POST':
        mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
        msg = {
            'id': mid,
            'ticket_id': tid,
            'sender': session.get('username', 'user'),
            'message': request.json['message'],
            'created_at': datetime.now().isoformat()
        }
        db['ticket_messages'].append(msg)
        save_db(db)
        return jsonify({'success': True})

    messages = [m for m in db['ticket_messages'] if m['ticket_id'] == tid]
    return jsonify(messages)


@app.route('/api/balance')
@login_required
def api_balance():
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == session['user_id']), None)
    return jsonify({'balance': user.get('balance', 0) if user else 0})


@app.route('/api/balance/add', methods=['POST'])
@login_required
def api_balance_add():
    db = load_db()
    user = next((u for u in db['users'] if u['id'] == session['user_id']), None)
    if user:
        amount = float(request.json.get('amount', 0))
        user['balance'] = user.get('balance', 0) + amount
        save_db(db)
    return jsonify({'success': True})


@app.route('/api/cdn-request', methods=['POST'])
@login_required
def api_cdn_request():
    db = load_db()
    data = request.json
    rid = max([r['id'] for r in db['cdn_requests']], default=0) + 1
    req = {
        'id': rid,
        'user_id': session['user_id'],
        'status': 'pending',
        'created_at': datetime.now().isoformat(),
        **data
    }
    db['cdn_requests'].append(req)
    save_db(db)
    return jsonify({'success': True})


# Admin API
@app.route('/api/admin/services', methods=['GET'])
@admin_required
def api_admin_services():
    db = load_db()
    services = db['services']
    for s in services:
        user = next((u for u in db['users'] if u['id'] == s['owner_id']), None)
        s['owner_username'] = user['username'] if user else 'Unknown'
    return jsonify(services)


@app.route('/api/admin/services/<int:sid>/activate', methods=['POST'])
@admin_required
def api_admin_activate(sid):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == sid), None)
    if service:
        service.update(request.json)
        service['status'] = 'active'
        service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
        save_db(db)
    return jsonify({'success': True})


@app.route('/api/admin/services/<int:sid>/renew', methods=['POST'])
@admin_required
def api_admin_renew(sid):
    db = load_db()
    service = next((s for s in db['services'] if s['id'] == sid), None)
    if service:
        service['status'] = 'active'
        service['expires_at'] = (datetime.now() + timedelta(days=30)).isoformat()
        save_db(db)
    return jsonify({'success': True})


@app.route('/api/admin/tickets')
@admin_required
def api_admin_tickets():
    db = load_db()
    tickets = db['tickets']
    for t in tickets:
        user = next((u for u in db['users'] if u['id'] == t['user_id']), None)
        t['username'] = user['username'] if user else 'Unknown'
    return jsonify(tickets)


@app.route('/api/admin/tickets/<int:tid>/messages', methods=['GET', 'POST'])
@admin_required
def api_admin_ticket_messages(tid):
    db = load_db()

    if request.method == 'POST':
        mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
        msg = {
            'id': mid,
            'ticket_id': tid,
            'sender': 'admin',
            'message': request.json['message'],
            'created_at': datetime.now().isoformat()
        }
        db['ticket_messages'].append(msg)
        save_db(db)
        return jsonify({'success': True})

    messages = [m for m in db['ticket_messages'] if m['ticket_id'] == tid]
    return jsonify(messages)


@app.route('/api/admin/cdn-requests')
@admin_required
def api_admin_cdn():
    return jsonify(load_db()['cdn_requests'])


@app.route('/api/admin/cdn-requests/<int:rid>/activate', methods=['POST'])
@admin_required
def api_admin_cdn_activate(rid):
    db = load_db()
    cdn_req = next((r for r in db['cdn_requests'] if r['id'] == rid), None)
    if cdn_req:
        cdn_req['status'] = 'active'

        # Создать тикет
        tid = max([t['id'] for t in db['tickets']], default=0) + 1
        ticket = {
            'id': tid,
            'user_id': cdn_req['user_id'],
            'subject': f"CDN активирован: {cdn_req['website_url']}",
            'priority': 'high',
            'status': 'open',
            'created_at': datetime.now().isoformat()
        }
        db['tickets'].append(ticket)

        # Первое сообщение от админа
        mid = max([m['id'] for m in db['ticket_messages']], default=0) + 1
        msg = {
            'id': mid,
            'ticket_id': tid,
            'sender': 'admin',
            'message': f"Здравствуйте! Ваш CDN запрос одобрен.\n\nДетали:\n• Сайт: {cdn_req['website_url']}\n• Трафик: {cdn_req['monthly_traffic']}\n• Скорость: {cdn_req['required_speed']}\n\nСвяжемся для настройки.",
            'created_at': datetime.now().isoformat()
        }
        db['ticket_messages'].append(msg)

        save_db(db)
    return jsonify({'success': True})


# Init DB
def init_db():
    db = load_db()
    if not db['users']:
        db['users'].append({
            'id': 1,
            'username': 'admin',
            'password': bcrypt.hashpw('admin'.encode(), bcrypt.gensalt()).decode(),
            'is_admin': True,
            'balance': 999999.0
        })
        db['users'].append({
            'id': 2,
            'username': 'testuser',
            'password': bcrypt.hashpw('testpassword'.encode(), bcrypt.gensalt()).decode(),
            'is_admin': False,
            'balance': 50.0
        })
        save_db(db)
        print('✓ DB initialized: admin/admin, testuser/testpassword')


if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=8000)