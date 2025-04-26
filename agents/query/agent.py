"""
Agente para consulta de preços de produtos.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from data.models import ShoppingList, ShoppingItem
from storage.operations import BigQueryOperations

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Definir o schema de estado
class QueryState(TypedDict):
    """Estado do agente de consulta."""
    shopping_list: ShoppingList
    price_options: Dict[str, List[Dict[str, Any]]]
    products_not_found: List[str]
    error: Optional[str]

def query_prices(state: QueryState) -> QueryState:
    """
    Consulta preços para os produtos na lista de compras.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        shopping_list = state["shopping_list"]
        db_ops = BigQueryOperations()
        
        price_options = {}
        products_not_found = []
        
        for item in shopping_list.items:
            product_name = item.product_name
            logger.info(f"Consultando preços para o produto: {product_name}")
            
            prices = db_ops.get_all_prices_for_product(product_name)
            
            if prices:
                price_options[product_name] = prices
            else:
                products_not_found.append(product_name)
                logger.warning(f"Produto não encontrado: {product_name}")
        
        logger.info(f"Encontrados preços para {len(price_options)} produtos")
        logger.info(f"Produtos não encontrados: {len(products_not_found)}")
        
        return {
            "shopping_list": shopping_list,
            "price_options": price_options,
            "products_not_found": products_not_found,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao consultar preços: {str(e)}"
        logger.error(error_message)
        return {
            "shopping_list": state["shopping_list"],
            "price_options": {},
            "products_not_found": [],
            "error": error_message
        }

def create_graph() -> StateGraph:
    """
    Cria o grafo de estado para o agente de consulta.
    
    Returns:
        Grafo de estado compilado
    """
    # Criar grafo de estado
    workflow = StateGraph(QueryState)
    
    # Adicionar nós
    workflow.add_node("query_prices", query_prices)
    
    # Definir o nó de entrada
    workflow.set_entry_point("query_prices")
    
    # Adicionar arestas
    workflow.add_edge("query_prices", END)
    
    # Compilar grafo
    return workflow.compile()

def run_query_agent(shopping_list: ShoppingList) -> Dict[str, Any]:
    """
    Executa o agente de consulta para obter preços de produtos.
    
    Args:
        shopping_list: Lista de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({
            "shopping_list": shopping_list,
            "price_options": {},
            "products_not_found": [],
            "error": None
        })
        
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"]
            }
        
        if not result.get("price_options"):
            return {
                "success": False,
                "error": "Nenhum produto encontrado"
            }
        
        return {
            "success": True,
            "price_options": result.get("price_options", {}),
            "products_not_found": result.get("products_not_found", [])
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de consulta: {str(e)}"
        logger.error(error_message)
        return {
            "success": False,
            "error": error_message
        }
