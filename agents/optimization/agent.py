"""
Agente para otimização de compras (versão simplificada sem cálculo de quantidades).
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

# Definir o schema de estado (atualizado para incluir total_requested_items)
class OptimizationState(TypedDict):
    """Estado do agente de otimização."""
    price_options: Dict[str, List[Dict[str, Any]]]  # Opções de preço
    products_not_found: List[str]  # Produtos não encontrados
    total_requested_items: int  # Total de itens solicitados originalmente
    recommendation: Optional[Dict[str, Any]]
    error: Optional[str]

def find_best_single_store(state: OptimizationState) -> OptimizationState:
    """
    Encontra a melhor opção de compra em um único supermercado (baseado na soma dos preços unitários).
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state["price_options"]
        products_not_found = state.get("products_not_found", [])
        total_requested_items = state.get("total_requested_items", 0)  # Obter o total de itens
        
        # Calcular a soma dos preços unitários para cada supermercado
        # Considerando apenas os produtos que estão disponíveis em cada supermercado
        supermarket_totals = {}
        supermarket_items_found = {}
        all_supermarkets = set()

        # Primeiro, identificar todos os supermercados que têm pelo menos um item
        for product_name, options in price_options.items():
            for option in options:
                all_supermarkets.add(option["supermarket_name"])

        # Agora, calcular o total para cada supermercado, somando os preços dos itens disponíveis nele
        for supermarket_name in all_supermarkets:
            current_total = 0.0
            items_in_this_store = []
            products_in_this_store = set()
            
            # Iterar por todos os produtos da lista original
            for product_name, options in price_options.items():
                # Encontrar a opção (se existir) para este produto neste supermercado
                option_in_this_store = None
                for option in options:
                    if option["supermarket_name"] == supermarket_name:
                        option_in_this_store = option
                        break # Pega a primeira ocorrência (assumindo que não há duplicatas por produto/supermercado)
                
                if option_in_this_store:
                    price = option_in_this_store["price"] # Usar o preço unitário diretamente
                    current_total += price
                    
                    # Adicionar item formatado à lista deste supermercado
                    items_in_this_store.append(option_in_this_store)
                    products_in_this_store.add(product_name)

            # Armazenar o total e os itens encontrados para este supermercado
            if items_in_this_store: # Apenas considerar supermercados onde encontramos itens
                supermarket_totals[supermarket_name] = current_total
                supermarket_items_found[supermarket_name] = items_in_this_store
        
        if not supermarket_totals:
            error_message = "Não foi possível calcular os totais (soma de preços unitários) para nenhum supermercado."
            logger.error(error_message)
            return {
                "price_options": price_options,
                "products_not_found": products_not_found,
                "total_requested_items": total_requested_items,  # Manter o total de itens
                "recommendation": None,
                "error": error_message
            }

        # Encontrar o supermercado com a menor soma de preços unitários
        best_supermarket = min(supermarket_totals.items(), key=lambda x: x[1])
        best_supermarket_name = best_supermarket[0]
        best_supermarket_total = best_supermarket[1]
        
        # Criar opção de supermercado com a lista CORRETA de itens encontrados nele
        single_store_option = {
            "supermarket_name": best_supermarket_name,
            "total_price": best_supermarket_total, # Representa a soma dos preços unitários
            "items": supermarket_items_found[best_supermarket_name] # Usar a lista de itens encontrada
        }
        
        logger.info(f"Melhor supermercado (soma unitária): {best_supermarket_name}, Soma total: {best_supermarket_total:.2f}")
        
        return {
            "price_options": price_options,
            "products_not_found": products_not_found,
            "total_requested_items": total_requested_items,  # Manter o total de itens
            "recommendation": {
                "single_store_option": single_store_option,
                "multi_store_option": [],  # Será preenchido pelo próximo nó
                "savings": 0.0,
                "savings_percentage": 0.0,
                "products_not_found": products_not_found,
                "total_requested_items": total_requested_items  # Incluir o total de itens na recomendação
            },
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao encontrar melhor supermercado (soma unitária): {str(e)}"
        logger.exception(error_message) # Usar exception para logar traceback
        return {
            "price_options": state.get("price_options", {}),
            "products_not_found": state.get("products_not_found", []),
            "total_requested_items": state.get("total_requested_items", 0),  # Manter o total de itens
            "recommendation": None,
            "error": error_message
        }

def find_best_multi_store(state: OptimizationState) -> OptimizationState:
    """
    Encontra a melhor opção de compra em múltiplos supermercados (baseado na soma dos menores preços unitários).
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state["price_options"]
        recommendation = state["recommendation"]
        products_not_found = state.get("products_not_found", [])
        total_requested_items = state.get("total_requested_items", 0)  # Obter o total de itens
        
        if not recommendation:
            raise ValueError("Recomendação de único supermercado não encontrada")
        
        single_store_option = recommendation["single_store_option"]
        single_store_total = single_store_option["total_price"] # Soma unitária do melhor supermercado único
        
        # Encontrar o menor preço unitário para cada produto
        best_prices = {}
        for product_name, options in price_options.items():
            if options: # Garante que há opções para o produto
                best_option = min(options, key=lambda x: x["price"])
                best_prices[product_name] = best_option
        
        # Agrupar por supermercado
        supermarket_items = {}
        multi_store_total = 0.0 # Soma dos menores preços unitários
        
        for product_name, option in best_prices.items():
            supermarket_name = option["supermarket_name"]
            price = option["price"] # Preço unitário
            
            if supermarket_name not in supermarket_items:
                supermarket_items[supermarket_name] = []
            
            # Adicionar a opção completa (sem modificar)
            supermarket_items[supermarket_name].append(option)
            multi_store_total += price
        
        # Criar opções de supermercado
        multi_store_options = []
        
        for supermarket_name, items in supermarket_items.items():
            total_price = sum(item["price"] for item in items) # Soma unitária por supermercado
            
            multi_store_options.append({
                "supermarket_name": supermarket_name,
                "total_price": total_price,
                "items": items
            })
        
        # Calcular economia (comparando soma unitária)
        savings = single_store_total - multi_store_total
        savings_percentage = (savings / single_store_total) * 100 if single_store_total > 0 else 0.0
        
        logger.info(f"Economia com múltiplos supermercados (soma unitária): {savings:.2f} ({savings_percentage:.2f}%)")
        
        # Atualizar recomendação
        recommendation["multi_store_option"] = multi_store_options
        recommendation["savings"] = savings
        recommendation["savings_percentage"] = savings_percentage
        recommendation["total_requested_items"] = total_requested_items  # Garantir que o total está na recomendação
        
        return {
            "price_options": price_options,
            "products_not_found": products_not_found,
            "total_requested_items": total_requested_items,  # Manter o total de itens
            "recommendation": recommendation,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao encontrar melhor opção de múltiplos supermercados (soma unitária): {str(e)}"
        logger.exception(error_message) # Usar exception para logar traceback
        return {
            "price_options": state.get("price_options", {}),
            "products_not_found": state.get("products_not_found", []),
            "total_requested_items": state.get("total_requested_items", 0),  # Manter o total de itens
            "recommendation": state.get("recommendation"),
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
    products_not_found: List[str],
    total_requested_items: int = 0,  # Novo parâmetro com valor padrão
) -> Dict[str, Any]:
    """
    Executa o agente de otimização para encontrar as melhores opções de compra (comparação de preços unitários).
    
    Args:
        price_options: Opções de preço para cada produto
        products_not_found: Lista de produtos não encontrados
        total_requested_items: Total de itens solicitados originalmente
        
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
            "total_requested_items": total_requested_items,  # Incluir o total de itens
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
        error_message = f"Erro ao executar agente de otimização (simplificado): {str(e)}"
        logger.exception(error_message) # Usar exception para logar traceback
        return {
            "success": False,
            "error": error_message
        }