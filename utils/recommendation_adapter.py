"""
Adaptador para converter a saída do agente de otimização para o formato esperado pelo agente de resposta.
"""

import logging
from typing import Dict, Any, List, Optional

# Configuração do logger
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

def adapt_recommendation(optimization_recommendation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converte a saída do agente de otimização para o formato esperado pelo agente de resposta.
    
    Args:
        optimization_recommendation: Recomendação do agente de otimização
        
    Returns:
        Recomendação no formato esperado pelo agente de resposta
    """
    logger.info("Adaptando recomendação do agente de otimização para o agente de resposta")
    
    # Verificar se a recomendação é válida
    if not optimization_recommendation or not isinstance(optimization_recommendation, dict):
        logger.error("Recomendação inválida ou vazia")
        return {}
        
    # Inicializar estrutura de saída
    adapted_recommendation = {
        "single_store_option": None,
        "multi_store_option": [],
        "savings": 0.0,
        "savings_percentage": 0.0,
        "products_not_found": optimization_recommendation.get("products_not_found", []),
        "num_items_requested": optimization_recommendation.get("num_items_requested", 0),
        "num_multi_store_items_found": 0
    }
    
    # Processamento baseado no tipo de recomendação
    rec_type = optimization_recommendation.get("type")
    
    # Adaptar recomendação de mercado único
    if rec_type == "single_store":
        single_store_option = {
            "supermarket_name": optimization_recommendation.get("store", "Desconhecido"),
            "total_price": optimization_recommendation.get("total_cost", 0.0),
            "num_items_found": optimization_recommendation.get("num_items_found", 0),
            "items": []
        }
        
        # Adaptar itens
        for item in optimization_recommendation.get("items", []):
            adapted_item = {
                "product_name": item.get("product_name", ""),
                "price": item.get("price", 0.0),
                # Campos opcionais esperados pelo agente de resposta
                "valid_until": None,
                "folder_link": None,
                "observations": None
            }
            single_store_option["items"].append(adapted_item)
            
        adapted_recommendation["single_store_option"] = single_store_option
    
    # Adaptar recomendação de múltiplos mercados
    # Mesmo que a recomendação final não seja multi_store, nós adaptamos para o formato esperado
    # para que o agente de resposta possa mostrar ambas as opções
    
    # Agrupar itens por loja
    store_items = {}
    for item in optimization_recommendation.get("items", []):
        store = item.get("store", "Desconhecido")
        if store not in store_items:
            store_items[store] = []
        store_items[store].append(item)
    
    # Criar estrutura de múltiplos mercados
    multi_store_option = []
    num_multi_items_found = 0
    
    # Se a recomendação original for multi_store, usamos as lojas originais
    # Caso contrário, criamos uma representação alternativa
    if rec_type == "multi_store":
        # Para cada loja, criar uma entrada no formato esperado
        for store, items in store_items.items():
            store_option = {
                "supermarket_name": store,
                "total_price": sum(item.get("price", 0.0) for item in items),
                "num_items_found": len(items),
                "items": []
            }
            
            # Adaptar itens
            for item in items:
                adapted_item = {
                    "product_name": item.get("product_name", ""),
                    "price": item.get("price", 0.0),
                    # Campos opcionais esperados pelo agente de resposta
                    "valid_until": None,
                    "folder_link": None,
                    "observations": None
                }
                store_option["items"].append(adapted_item)
                
            multi_store_option.append(store_option)
            num_multi_items_found += len(items)
    
    adapted_recommendation["multi_store_option"] = multi_store_option
    adapted_recommendation["num_multi_store_items_found"] = num_multi_items_found
    
    # Calcular economia (se ambas as opções estiverem disponíveis)
    if adapted_recommendation["single_store_option"] and multi_store_option:
        single_price = adapted_recommendation["single_store_option"]["total_price"]
        multi_price = sum(store["total_price"] for store in multi_store_option)
        
        savings = single_price - multi_price
        adapted_recommendation["savings"] = savings
        
        # Calcular porcentagem de economia
        if single_price > 0:
            savings_percentage = (savings / single_price) * 100
            adapted_recommendation["savings_percentage"] = savings_percentage
    
    logger.info("Adaptação de recomendação concluída")
    return adapted_recommendation