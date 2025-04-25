"""
Agente para otimização de compras.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from collections import defaultdict

from data.models import SupermarketOption, PriceOption

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def find_best_single_store(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encontra o melhor supermercado para comprar todos os produtos.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state.get("price_options", {})
        
        if not price_options:
            state["success"] = False
            state["error"] = "Opções de preço não encontradas"
            return state
        
        # Agrupar produtos por supermercado
        supermarket_products = defaultdict(list)
        
        for product_name, options in price_options.items():
            for option in options:
                supermarket_name = option.get("supermarket_name")
                supermarket_products[supermarket_name].append(option)
        
        # Encontrar supermercado com mais produtos
        best_supermarket = None
        best_products = []
        best_total = float('inf')
        
        for supermarket_name, products in supermarket_products.items():
            # Verificar se o supermercado tem todos os produtos
            product_names = set(p.get("product_name") for p in products)
            if len(product_names) == len(price_options):
                # Calcular preço total
                total_price = sum(p.get("price", 0) for p in products)
                
                if total_price < best_total:
                    best_total = total_price
                    best_supermarket = supermarket_name
                    best_products = products
        
        # Se não encontrou um supermercado com todos os produtos,
        # escolher o que tem mais produtos
        if not best_supermarket:
            max_products = 0
            for supermarket_name, products in supermarket_products.items():
                product_names = set(p.get("product_name") for p in products)
                if len(product_names) > max_products:
                    max_products = len(product_names)
                    best_supermarket = supermarket_name
                    best_products = products
                    best_total = sum(p.get("price", 0) for p in products)
        
        # Atualizar estado
        state["single_store_option"] = {
            "supermarket_name": best_supermarket,
            "total_price": best_total,
            "items": best_products
        }
        
        logger.info(f"Melhor supermercado: {best_supermarket}, Preço total: {best_total}")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao encontrar melhor supermercado: {str(e)}")
        state["error"] = f"Erro ao encontrar melhor supermercado: {str(e)}"
        return state

def find_best_multi_store(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Encontra a melhor combinação de supermercados para comprar os produtos.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        price_options = state.get("price_options", {})
        single_store_option = state.get("single_store_option", {})
        
        if not price_options or not single_store_option:
            state["success"] = False
            state["error"] = "Opções de preço ou opção de supermercado único não encontradas"
            return state
        
        # Encontrar o melhor preço para cada produto
        best_options = []
        
        for product_name, options in price_options.items():
            if options:
                # Ordenar por preço
                sorted_options = sorted(options, key=lambda x: x.get("price", float('inf')))
                best_options.append(sorted_options[0])
        
        # Agrupar por supermercado
        supermarket_options = defaultdict(list)
        
        for option in best_options:
            supermarket_name = option.get("supermarket_name")
            supermarket_options[supermarket_name].append(option)
        
        # Criar opções de supermercado
        multi_store_option = []
        
        for supermarket_name, products in supermarket_options.items():
            total_price = sum(p.get("price", 0) for p in products)
            
            multi_store_option.append({
                "supermarket_name": supermarket_name,
                "total_price": total_price,
                "items": products
            })
        
        # Calcular economia
        multi_store_total = sum(option.get("total_price", 0) for option in multi_store_option)
        single_store_total = single_store_option.get("total_price", 0)
        
        savings = single_store_total - multi_store_total
        savings_percentage = (savings / single_store_total * 100) if single_store_total > 0 else 0
        
        # Atualizar estado
        state["multi_store_option"] = multi_store_option
        state["savings"] = savings
        state["savings_percentage"] = round(savings_percentage, 2)
        
        logger.info(f"Economia: {savings} ({savings_percentage:.2f}%)")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao encontrar melhor combinação de supermercados: {str(e)}")
        state["error"] = f"Erro ao encontrar melhor combinação de supermercados: {str(e)}"
        return state

def create_recommendation(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Cria a recomendação final.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        single_store_option = state.get("single_store_option", {})
        multi_store_option = state.get("multi_store_option", [])
        savings = state.get("savings", 0)
        savings_percentage = state.get("savings_percentage", 0)
        products_not_found = state.get("products_not_found", [])
        
        # Criar recomendação
        recommendation = {
            "single_store_option": single_store_option,
            "multi_store_option": multi_store_option,
            "savings": savings,
            "savings_percentage": savings_percentage,
            "products_not_found": products_not_found
        }
        
        # Atualizar estado
        state["recommendation"] = recommendation
        state["success"] = True
        
        logger.info("Recomendação criada com sucesso")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao criar recomendação: {str(e)}")
        state["success"] = False
        state["error"] = f"Erro ao criar recomendação: {str(e)}"
        return state

def create_optimization_graph() -> StateGraph:
    """
    Cria o grafo de otimização.
    
    Returns:
        Grafo de otimização
    """
    # Definir grafo
    workflow = StateGraph(name="optimization")
    
    # Adicionar nós
    workflow.add_node("find_best_single_store", find_best_single_store)
    workflow.add_node("find_best_multi_store", find_best_multi_store)
    workflow.add_node("create_recommendation", create_recommendation)
    
    # Definir arestas
    workflow.set_entry_point("find_best_single_store")
    workflow.add_edge("find_best_single_store", "find_best_multi_store")
    workflow.add_edge("find_best_multi_store", "create_recommendation")
    workflow.add_edge("create_recommendation", END)
    
    # Compilar grafo
    return workflow.compile()

def run_optimization_agent(price_options: Dict[str, List[Dict[str, Any]]], products_not_found: List[str]) -> Dict[str, Any]:
    """
    Executa o agente de otimização.
    
    Args:
        price_options: Opções de preço por produto
        products_not_found: Produtos não encontrados
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_optimization_graph()
        
        # Executar grafo
        result = graph.invoke({
            "price_options": price_options,
            "products_not_found": products_not_found
        })
        
        if result.get("success", False):
            logger.info("Agente de otimização executado com sucesso")
            return result
        else:
            logger.error(f"Erro no agente de otimização: {result.get('error')}")
            return result
    
    except Exception as e:
        logger.error(f"Erro ao executar agente de otimização: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao executar agente de otimização: {str(e)}"
        }
