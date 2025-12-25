from pydantic import BaseModel, EmailStr
from typing import Optional, Literal
from datetime import datetime


# User models
class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_admin: bool = False
    balance: float = 0.0


# Service models
class ServiceBase(BaseModel):
    service_type: Literal["VPS", "DEDICATED", "VPN", "VDesktop", "S3"]
    price: str


class ServiceCreate(ServiceBase):
    os: Optional[str] = None
    plan: Optional[str] = None
    cpu: Optional[str] = None
    ram: Optional[str] = None
    disk: Optional[str] = None
    region: Optional[str] = None
    datacenter: Optional[str] = None
    network: Optional[str] = None
    setup_fee: Optional[str] = None
    premium_support: Optional[bool] = False
    vpn_country: Optional[str] = None
    vpn_protocol: Optional[str] = None
    s3_type: Optional[str] = None
    s3_size: Optional[int] = None
    vdesktop_pause: Optional[bool] = None


class Service(ServiceBase):
    id: int
    name: str
    owner_id: int
    status: Literal["pending", "active", "expiring_soon", "expired"] = "pending"
    created_at: str
    expires_at: Optional[str] = None


# Ticket models
class TicketCreate(BaseModel):
    subject: str
    message: str
    priority: Optional[Literal["low", "medium", "high", "urgent"]] = "medium"
    category: Optional[Literal["technical", "billing", "general", "sales"]] = "general"


class Ticket(BaseModel):
    id: int
    user_id: int
    subject: str
    priority: Literal["low", "medium", "high", "urgent"]
    category: Literal["technical", "billing", "general", "sales"]
    status: Literal["open", "in_progress", "waiting", "closed"] = "open"
    created_at: str
    updated_at: Optional[str] = None


# Message models
class MessageCreate(BaseModel):
    message: str


class Message(BaseModel):
    id: int
    ticket_id: Optional[int] = None
    chat_id: Optional[int] = None
    sender: str
    sender_type: Literal["user", "admin"] = "user"
    message: str
    created_at: str
    is_read: bool = False


# Live Chat models
class ChatCreate(BaseModel):
    pass


class Chat(BaseModel):
    id: int
    user_id: int
    status: Literal["active", "closed"] = "active"
    created_at: str
    closed_at: Optional[str] = None


# Transaction models
class TransactionCreate(BaseModel):
    amount: float
    description: str


class Transaction(BaseModel):
    id: int
    user_id: int
    amount: float
    description: str
    created_at: str
    type: Literal["credit", "debit"] = "debit"


# CDN Request models
class CDNRequestCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    country: str
    website_url: str
    description: str
    monthly_traffic: str
    required_speed: str


class CDNRequest(BaseModel):
    id: int
    user_id: int
    status: Literal["pending", "active", "rejected"] = "pending"
    created_at: str
    first_name: str
    last_name: str
    phone: str
    email: str
    country: str
    website_url: str
    description: str
    monthly_traffic: str
    required_speed: str


# Balance models
class BalanceAdd(BaseModel):
    amount: float


# Admin activation models
class ServiceActivation(BaseModel):
    ip: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = None
    vpn_key: Optional[str] = None
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    vdesktop_ip: Optional[str] = None


# Notification models
class Notification(BaseModel):
    id: int
    user_id: int
    type: Literal["info", "success", "warning", "error"]
    title: str
    message: str
    is_read: bool = False
    created_at: str
    link: Optional[str] = None
