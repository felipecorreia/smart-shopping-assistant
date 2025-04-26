"""
Agente para otimização de compras.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END
from data.models import SupermarketOption, PriceOption, ShoppingRecommendation

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Definir o schema de estado
class OptimizationState(TypedDict):
    """Estado do agente de otimização."""
    price_options: Dict[str, List[Dict[str, Any]]]
    products_not_found: List[str]
    recommendation: Optional[Dict[str, Any]]
    error: Optional[str]

def find_best_single_store(state: OptimizationState) -> OptimizationState:
    """
    Encontra a melhor opção de compra em um único supermercado.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state["price_options"]
        
        # Calcular o preço total para cada supermercado
        supermarket_totals = {}
        supermarket_items = {}
        
        for product_name, options in price_options.items():
            for option in options:
                supermarket_name = option["supermarket_name"]
                price = option["price"]
                
                if supermarket_name not in supermarket_totals:
                    supermarket_totals[supermarket_name] = 0
                    supermarket_items[supermarket_name] = []
                
                supermarket_totals[supermarket_name] += price
                supermarket_items[supermarket_name].append(option)
        
        # Encontrar o supermercado com o menor preço total
        best_supermarket = min(supermarket_totals.items(), key=lambda x: x[1])
        best_supermarket_name = best_supermarket[0]
        best_supermarket_total = best_supermarket[1]
        
        # Criar opção de supermercado
        single_store_option = {
            "supermarket_name": best_supermarket_name,
            "total_price": best_supermarket_total,
            "items": supermarket_items[best_supermarket_name]
        }
        
        logger.info(f"Melhor supermercado: {best_supermarket_name}, Preço total: {best_supermarket_total}")
        
        return {
            "price_options": price_options,
            "products_not_found": state["products_not_found"],
            "recommendation": {
                "single_store_option": single_store_option,
                "multi_store_option": [],
                "savings": 0.0,
                "savings_percentage": 0.0,
                "products_not_found": state["products_not_found"]
            },
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao encontrar melhor supermercado: {str(e)}"
        logger.error(error_message)
        return {
            "price_options": state["price_options"],
            "products_not_found": state["products_not_found"],
            "recommendation": None,
            "error": error_message
        }

def find_best_multi_store(state: OptimizationState) -> OptimizationState:
    """
    Encontra a melhor opção de compra em múltiplos supermercados.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state["price_options"]
        recommendation = state["recommendation"]
        
        if not recommendation:
            raise ValueError("Recomendação de único supermercado não encontrada")
        
        single_store_option = recommendation["single_store_option"]
        single_store_total = single_store_option["total_price"]
        
        # Encontrar o melhor preço para cada produto
        best_prices = {}
        for product_name, options in price_options.items():
            best_option = min(options, key=lambda x: x["price"])
            best_prices[product_name] = best_option
        
        # Agrupar por supermercado
        supermarket_items = {}
        for product_name, option in best_prices.items():
            supermarket_name = option["supermarket_name"]
            
            if supermarket_name not in supermarket_items:
                supermarket_items[supermarket_name] = []
            
            supermarket_items[supermarket_name].append(option)
        
        # Criar opções de supermercado
        multi_store_options = []
        multi_store_total = 0.0
        
        for supermarket_name, items in supermarket_items.items():
            total_price = sum(item["price"] for item in items)
            multi_store_total += total_price
            
            multi_store_options.append({
                "supermarket_name": supermarket_name,
                "total_price": total_price,
                "items": items
            })
        
        # Calcular economia
        savings = single_store_total - multi_store_total
        savings_percentage = (savings / single_store_total) * 100 if single_store_total > 0 else 0.0
        
        logger.info(f"Economia com múltiplos supermercados: {savings:.2f} ({savings_percentage:.2f}%)")
        
        # Atualizar recomendação
        recommendation["multi_store_option"] = multi_store_options
        recommendation["savings"] = savings
        recommendation["savings_percentage"] = savings_percentage
        
        return {
            "price_options": price_options,
            "products_not_found": state["products_not_found"],
            "recommendation": recommendation,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao encontrar melhor opção de múltiplos supermercados: {str(e)}"
        logger.error(error_message)
        return {
            "price_options": state["price_options"],
            "products_not_found": state["products_not_found"],
            "recommendation": state["recommendation"],
            "error": error_message
        }

def create_graph() -> StateGraph:
    """
    Cria o grafo de estado para o agente de otimização.
    
    Returns:
        Grafo de estado compilado
    """
    # Criar grafo de estado
    workflow = StateGraph(OptimizationState)
    
    # Adicionar nós
    workflow.add_node("find_best_single_store", find_best_single_store)
    workflow.add_node("find_best_multi_store", find_best_multi_store)
    
    # Definir o nó de entrada
    workflow.set_entry_point("find_best_single_store")
    
    # Adicionar arestas
    workflow.add_edge("find_best_single_store", "find_best_multi_store")
    workflow.add_edge("find_best_multi_store", END)
    
    # Compilar grafo
    return workflow.compile()

def run_optimization_agent(
    price_options: Dict[str, List[Dict[str, Any]]],
    products_not_found: List[str]
) -> Dict[str, Any]:
    """
    Executa o agente de otimização para encontrar as melhores opções de compra.
    
    Args:
        price_options: Opções de preço para cada produto
        products_not_found: Lista de produtos não encontrados
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({
            "price_options": price_options,
            "products_not_found": products_not_found,
            "recommendation": None,
            "error": None
        })
        
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"]
            }
        
        if not result.get("recommendation"):
            return {
                "success": False,
                "error": "Não foi possível gerar uma recomendação"
            }
        
        return {
            "success": True,
            "recommendation": result["recommendation"]
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de otimização: {str(e)}"
        logger.error(error_message)
        return {
            "success": False,
            "error": error_message
        }
