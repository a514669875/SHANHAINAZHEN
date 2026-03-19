"""Supplier model."""
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class Supplier(Base):
    __tablename__ = "t_supplier"

    id = Column(Integer, primary_key=True, autoincrement=True)
    procurement_id = Column(Integer, ForeignKey("t_procurement.id", ondelete="CASCADE"), nullable=False)
    supplier_name = Column(String(255))
    contact_person = Column(String(100))
    contact_phone = Column(String(50))
    business_scope = Column(String(500))
    tax_rate = Column(String(20))
    quoted_price = Column(Float)
    rank = Column(Integer)  # 1, 2, 3...
    is_winner = Column(Boolean, default=False)
    contract_section = Column(String(50))  # 一标段/二标段

    procurement = relationship("Procurement", back_populates="suppliers")
