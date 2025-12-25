import json
import os
from typing import Dict, Any


DB_FILE = 'db.json'


def load_db() -> Dict[str, Any]:
    """Load database from JSON file"""
    try:
        if not os.path.exists(DB_FILE):
            return init_empty_db()
        with open(DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading database: {e}")
        return init_empty_db()


def save_db(db: Dict[str, Any]) -> None:
    """Save database to JSON file"""
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error saving database: {e}")


def init_empty_db() -> Dict[str, Any]:
    """Initialize empty database structure"""
    return {
        'users': [],
        'services': [],
        'tickets': [],
        'ticket_messages': [],
        'chats': [],
        'chat_messages': [],
        'cdn_requests': [],
        'transactions': [],
        'notifications': []
    }


def load_config() -> Dict[str, Any]:
    """Load configuration from JSON file"""
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


# User operations
def get_user_by_id(db: Dict[str, Any], user_id: int) -> Dict[str, Any] | None:
    """Get user by ID"""
    return next((u for u in db['users'] if u['id'] == user_id), None)


def get_user_by_username(db: Dict[str, Any], username: str) -> Dict[str, Any] | None:
    """Get user by username"""
    return next((u for u in db['users'] if u['username'] == username), None)


def create_user(db: Dict[str, Any], username: str, password_hash: str, is_admin: bool = False) -> Dict[str, Any]:
    """Create new user"""
    user_id = max([u['id'] for u in db['users']], default=0) + 1
    user = {
        'id': user_id,
        'username': username,
        'password': password_hash,
        'is_admin': is_admin,
        'balance': 50.0 if not is_admin else 999999.0
    }
    db['users'].append(user)
    return user


# Service operations
def get_user_services(db: Dict[str, Any], user_id: int) -> list:
    """Get all services for a user"""
    return [s for s in db['services'] if s['owner_id'] == user_id]


def get_service_by_id(db: Dict[str, Any], service_id: int, user_id: int = None) -> Dict[str, Any] | None:
    """Get service by ID, optionally filtered by user_id"""
    for s in db['services']:
        if s['id'] == service_id:
            if user_id is None or s['owner_id'] == user_id:
                return s
    return None


def create_service(db: Dict[str, Any], service_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new service"""
    service_id = max([s['id'] for s in db['services']], default=0) + 1
    service = {
        'id': service_id,
        **service_data
    }
    db['services'].append(service)
    return service


def delete_service(db: Dict[str, Any], service_id: int) -> bool:
    """Delete service"""
    original_len = len(db['services'])
    db['services'] = [s for s in db['services'] if s['id'] != service_id]
    return len(db['services']) < original_len


# Ticket operations
def get_user_tickets(db: Dict[str, Any], user_id: int) -> list:
    """Get all tickets for a user"""
    return [t for t in db['tickets'] if t['user_id'] == user_id]


def get_ticket_by_id(db: Dict[str, Any], ticket_id: int, user_id: int = None) -> Dict[str, Any] | None:
    """Get ticket by ID, optionally filtered by user_id"""
    for t in db['tickets']:
        if t['id'] == ticket_id:
            if user_id is None or t['user_id'] == user_id:
                return t
    return None


def create_ticket(db: Dict[str, Any], ticket_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new ticket"""
    ticket_id = max([t['id'] for t in db['tickets']], default=0) + 1
    ticket = {
        'id': ticket_id,
        **ticket_data
    }
    db['tickets'].append(ticket)
    return ticket


def get_ticket_messages(db: Dict[str, Any], ticket_id: int) -> list:
    """Get all messages for a ticket"""
    return [m for m in db['ticket_messages'] if m['ticket_id'] == ticket_id]


def create_ticket_message(db: Dict[str, Any], message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new ticket message"""
    msg_id = max([m['id'] for m in db['ticket_messages']], default=0) + 1
    message = {
        'id': msg_id,
        **message_data
    }
    db['ticket_messages'].append(message)
    return message


# Chat operations
def get_user_chat(db: Dict[str, Any], user_id: int, create_if_missing: bool = False) -> Dict[str, Any] | None:
    """Get active chat for user"""
    chat = next((c for c in db['chats'] if c['user_id'] == user_id and c['status'] == 'active'), None)
    if not chat and create_if_missing:
        from datetime import datetime
        chat_id = max([c['id'] for c in db['chats']], default=0) + 1
        chat = {
            'id': chat_id,
            'user_id': user_id,
            'status': 'active',
            'created_at': datetime.now().isoformat()
        }
        db['chats'].append(chat)
    return chat


def get_chat_messages(db: Dict[str, Any], chat_id: int) -> list:
    """Get all messages for a chat"""
    return [m for m in db['chat_messages'] if m['chat_id'] == chat_id]


def create_chat_message(db: Dict[str, Any], message_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new chat message"""
    msg_id = max([m['id'] for m in db['chat_messages']], default=0) + 1
    message = {
        'id': msg_id,
        **message_data
    }
    db['chat_messages'].append(message)
    return message


# Transaction operations
def get_user_transactions(db: Dict[str, Any], user_id: int) -> list:
    """Get all transactions for a user"""
    transactions = [t for t in db['transactions'] if t['user_id'] == user_id]
    return sorted(transactions, key=lambda x: x['created_at'], reverse=True)


def create_transaction(db: Dict[str, Any], transaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new transaction"""
    trans_id = max([t['id'] for t in db.get('transactions', [])], default=0) + 1
    transaction = {
        'id': trans_id,
        **transaction_data
    }
    db.setdefault('transactions', []).append(transaction)
    return transaction


# Notification operations
def get_user_notifications(db: Dict[str, Any], user_id: int, unread_only: bool = False) -> list:
    """Get notifications for a user"""
    notifications = [n for n in db.get('notifications', []) if n['user_id'] == user_id]
    if unread_only:
        notifications = [n for n in notifications if not n.get('is_read', False)]
    return sorted(notifications, key=lambda x: x['created_at'], reverse=True)


def create_notification(db: Dict[str, Any], notification_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new notification"""
    notif_id = max([n['id'] for n in db.get('notifications', [])], default=0) + 1
    notification = {
        'id': notif_id,
        **notification_data
    }
    db.setdefault('notifications', []).append(notification)
    return notification


def mark_notification_read(db: Dict[str, Any], notification_id: int, user_id: int) -> bool:
    """Mark notification as read"""
    for n in db.get('notifications', []):
        if n['id'] == notification_id and n['user_id'] == user_id:
            n['is_read'] = True
            return True
    return False


# CDN operations
def create_cdn_request(db: Dict[str, Any], cdn_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new CDN request"""
    cdn_id = max([r['id'] for r in db['cdn_requests']], default=0) + 1
    cdn_request = {
        'id': cdn_id,
        **cdn_data
    }
    db['cdn_requests'].append(cdn_request)
    return cdn_request


def get_cdn_request_by_id(db: Dict[str, Any], cdn_id: int) -> Dict[str, Any] | None:
    """Get CDN request by ID"""
    return next((r for r in db['cdn_requests'] if r['id'] == cdn_id), None)
