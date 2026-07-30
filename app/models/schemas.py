from sqlalchemy import Column, String, Integer, Float, Boolean, ForeignKey, Enum, DateTime
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import enum

Base = declarative_base()

class OrderStatus(enum.Enum):
    PENDING_PICKUP = "PENDING_PICKUP"
    IN_SHOP = "IN_SHOP"
    PROCESSING = "PROCESSING"
    READY = "READY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"

class OrderType(enum.Enum):
    PICKUP = "PICKUP"
    STORE_DROP = "STORE_DROP"

class PaymentStatus(enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"

class PaymentMode(enum.Enum):
    CASH = "CASH"
    UPI = "UPI"

class Customer(Base):
    __tablename__ = 'customers'
    customer_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    phone_number = Column(String, unique=True, index=True, nullable=False)
    saved_address = Column(String, nullable=True)
    last_location_gps = Column(String, nullable=True) # e.g., "lat,long"
    order_count = Column(Integer, default=0)
    preferred_language = Column(String, default="ENGLISH", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    orders = relationship("Order", back_populates="customer")
    point_transactions = relationship("PointTransaction", back_populates="customer")

class PointTransaction(Base):
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.customer_id"))
    order_id = Column(String, nullable=True) # Reference to the order that earned/redeemed it
    points = Column(Integer, default=0) # positive for EARNED, positive for REDEEMED (but transaction_type separates them)
    transaction_type = Column(String) # "EARNED" or "REDEEMED"
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer", back_populates="point_transactions")

class Order(Base):
    __tablename__ = 'orders'
    order_id = Column(String, primary_key=True, index=True) # e.g., "AC-1001"
    customer_id = Column(Integer, ForeignKey('customers.customer_id'), nullable=False)
    order_type = Column(Enum(OrderType), default=OrderType.PICKUP, nullable=False)
    status = Column(Enum(OrderStatus), default=OrderStatus.PENDING_PICKUP, nullable=False)
    item_count = Column(Integer, default=0)
    total_amount = Column(Float, nullable=True)
    payment_mode = Column(Enum(PaymentMode), nullable=True)
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING)
    disclaimer_accepted = Column(Boolean, default=False, nullable=False)
    runner_id = Column(Integer, nullable=True) # Could FK to a Users/Staff table
    service_category = Column(String, nullable=True)
    flat_address = Column(String, nullable=True)
    estimated_amount = Column(Float, nullable=True)
    delivery_fee = Column(Float, default=0.0)
    points_redeemed = Column(Integer, default=0)
    special_instructions = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    customer = relationship("Customer", back_populates="orders")
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = 'order_items'
    item_id = Column(Integer, primary_key=True, index=True)
    order_id = Column(String, ForeignKey('orders.order_id'), nullable=False)
    garment_type = Column(String, nullable=False)
    service_type = Column(String, nullable=False)
    quantity = Column(Integer, default=1)
    special_notes = Column(String, nullable=True)
    
    order = relationship("Order", back_populates="items")

class Runner(Base):
    __tablename__ = 'runners'
    runner_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone_number = Column(String, unique=True, index=True, nullable=False)
