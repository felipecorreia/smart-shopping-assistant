"""
Agente para consulta de produtos e preços no BigQuery.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from storage.operations import BigQueryOperations
from data.models import ShoppingList, ShoppingItem

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def query_prices(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Consulta preços para uma lista de compras.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        shopping_list = state.get("shopping_list")
        
        if not shopping_list:
            state["success"] = False
            state["error"] = "Lista de compras não encontrada"
            return state
        
        # Inicializar operações de banco de dados
        db_ops = BigQueryOperations()
        
        # Consultar preços
        price_options = {}
        products_not_found = []
        
        for item in shopping_list.items:
            product_name = item.product_name
            
            prices = db_ops.client.get_all_prices_for_product(product_name)
            
            if prices:
                price_options[product_name] = prices
            else:
                products_not_found.append(product_name)
        
        # Atualizar estado
        state["price_options"] = price_options
        state["products_not_found"] = products_not_found
        state["success"] = True
        
        logger.info(f"Preços consultados com sucesso: {len(price_options)} produtos encontrados, {len(products_not_found)} não encontrados")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao consultar preços: {str(e)}")
        state["success"] = False
        state["error"] = f"Erro ao consultar preços: {str(e)}"
        return state

def create_query_graph() -> StateGraph:
    """
    Cria o grafo de consulta.
    
    Returns:
        Grafo de consulta
    """
    # Definir grafo
    workflow = StateGraph(name="query")
    
    # Adicionar nós
    workflow.add_node("query_prices", query_prices)
    
    # Definir arestas
    workflow.set_entry_point("query_prices")
    workflow.add_edge("query_prices", END)
    
    # Compilar grafo
    return workflow.compile()

def run_query_agent(shopping_list: ShoppingList) -> Dict[str, Any]:
    """
    Executa o agente de consulta.
    
    Args:
        shopping_list: Lista de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_query_graph()
        
        # Executar grafo
        result = graph.invoke({"shopping_list": shopping_list})
        
        if result.get("success", False):
            logger.info("Agente de consulta executado com sucesso")
            return result
        else:
            logger.error(f"Erro no agente de consulta: {result.get('error')}")
            return result
    
    except Exception as e:
        logger.error(f"Erro ao executar agente de consulta: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao executar agente de consulta: {str(e)}"
        }
