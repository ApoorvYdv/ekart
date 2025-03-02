import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ...models import Base


class Permission(Base):
    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_role: Mapped[str] = mapped_column(String, nullable=True)
    permission_action: Mapped[str] = mapped_column(String, nullable=True)
    module: Mapped[str] = mapped_column(String, nullable=True)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True
    )
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    carts: Mapped[list["Cart"]] = relationship(
        "Cart", back_populates="user", cascade="all, delete-orphan"
    )
    orders: Mapped[list["OrderHistory"]] = relationship(
        "OrderHistory", back_populates="user", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Relationship
    products: Mapped[list["ProductInventory"]] = relationship(
        "ProductInventory", back_populates="category"
    )


class ProductInventory(Base):
    __tablename__ = "product_inventory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True
    )
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("category.id"), nullable=False
    )

    # Relationships
    category: Mapped["Category"] = relationship("Category", back_populates="products")
    carts: Mapped[list["Cart"]] = relationship("Cart", back_populates="product")
    orders: Mapped[list["OrderHistory"]] = relationship(
        "OrderHistory", back_populates="product"
    )


class Cart(Base):
    __tablename__ = "cart"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("product_inventory.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    added_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="carts")
    product: Mapped["ProductInventory"] = relationship(
        "ProductInventory", back_populates="carts"
    )


class OrderHistory(Base):
    __tablename__ = "order_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("product_inventory.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    order_date: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="orders")
    product: Mapped["ProductInventory"] = relationship(
        "ProductInventory", back_populates="orders"
    )


# @event.listens_for(Permission, "after_insert")
# @event.listens_for(Permission, "after_update")
# @event.listens_for(Permission, "after_delete")
# def permission_changes_listener(mapper, connection, target):
#     from ...controllers.manage_cache_dependency import update_cache

#     schema = connection.info.get("client_schema", None)

#     role = getattr(target, "user_role", None)  # Access the agency attribute
#     if role:
#         asyncio.create_task(update_cache(agency=schema, roles=[role]))
#     else:
#         print("No agency associated with this event.")
