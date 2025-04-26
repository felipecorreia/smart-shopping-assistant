"""
Módulo para definição de modelos de dados usando dataclasses.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ShoppingItem:
    """Item de compra com nome do produto, quantidade e unidade."""
    product_name: str
    quantity: float = 1.0
    unit: Optional[str] = None

@dataclass
class ShoppingList:
    """Lista de compras com itens."""
    items: List[ShoppingItem] = field(default_factory=list) 

@dataclass
class PriceOption:
    """Opção de preço para um produto em um supermercado."""
    product_name: str
    price: float
    supermarket_name: str
    unit: Optional[str] = None
    quantity: float = 1.0
    category: Optional[str] = None
    observations: Optional[str] = None
    folder_link: Optional[str] = None
    valid_until: Optional[str] = None

@dataclass
class SupermarketOption:
    """Opção de compra em um único supermercado."""
    supermarket_name: str
    total_price: float
    items: List[PriceOption] = field(default_factory=list)

@dataclass
class ShoppingRecommendation:
    """Recomendação de compras com opções de um único mercado ou múltiplos mercados."""
    single_store_option: SupermarketOption
    multi_store_option: List[SupermarketOption] = field(default_factory=list)
    savings: float = 0.0
    savings_percentage: float = 0.0
    products_not_found: List[str] = field(default_factory=list)
