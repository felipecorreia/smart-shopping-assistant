"""
Módulo para definição de esquemas de validação usando Pydantic.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, validator
from datetime import date

class ProductSchema(BaseModel):
    """Esquema para validação de produtos."""
    product_id: Optional[int] = None
    product_name: str
    price: float
    supermarket_name: str
    category: Optional[str] = None
    unit: Optional[str] = None
    quantity: float = 1.0
    observations: Optional[str] = None
    folder_link: Optional[str] = None
    valid_until: Optional[str] = None

    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('O preço deve ser positivo')
        return v

    @validator('quantity')
    def quantity_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('A quantidade deve ser positiva')
        return v

class ShoppingItemSchema(BaseModel):
    """Esquema para validação de itens de compra."""
    product_name: str
    quantity: float = 1.0
    unit: Optional[str] = None

class ShoppingListSchema(BaseModel):
    """Esquema para validação de listas de compra."""
    items: List[ShoppingItemSchema]

class PriceOptionSchema(BaseModel):
    """Esquema para validação de opções de preço."""
    product_name: str
    price: float
    supermarket_name: str
    unit: Optional[str] = None
    quantity: float = 1.0
    category: Optional[str] = None
    observations: Optional[str] = None
    folder_link: Optional[str] = None
    valid_until: Optional[str] = None

class SupermarketOptionSchema(BaseModel):
    """Esquema para validação de opções de supermercado."""
    supermarket_name: str
    total_price: float
    items: List[PriceOptionSchema]

class ShoppingRecommendationSchema(BaseModel):
    """Esquema para validação de recomendações de compra."""
    single_store_option: SupermarketOptionSchema
    multi_store_option: List[SupermarketOptionSchema]
    savings: float = 0.0
    savings_percentage: float = 0.0
    products_not_found: List[str] = []