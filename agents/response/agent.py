"""
Agente para formatação de resposta (versão simplificada sem cálculo de quantidades).
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
from langgraph.graph import StateGraph, END

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Definir o schema de estado
class ResponseState(TypedDict):
    """Estado do agente de resposta."""
    recommendation: Dict[str, Any]
    formatted_response: Optional[str]
    error: Optional[str]

def format_response(state: ResponseState) -> ResponseState:
    """
    Formata a resposta para o usuário (versão simplificada).
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        recommendation = state["recommendation"]
        
        if not recommendation:
            raise ValueError("Recomendação não encontrada")
        
        single_store_option = recommendation.get("single_store_option", {})
        multi_store_option = recommendation.get("multi_store_option", [])
        savings = recommendation.get("savings", 0.0)
        savings_percentage = recommendation.get("savings_percentage", 0.0)
        products_not_found = recommendation.get("products_not_found", [])
        total_requested_items = recommendation.get("total_requested_items", 0)  # Obter o total de itens solicitados
        
        # Calcular itens encontrados em cada opção
        single_store_items_count = len(single_store_option.get("items", []))
        
        # Para a opção multi_store, contar produtos únicos e calcular preço total
        multi_store_products = set()
        multi_store_total_price = 0.0
        products_counted = set()
        
        for store in multi_store_option:
            for item in store.get("items", []):
                product_name = item.get("product_name")
                multi_store_products.add(product_name)
                
                # Verificar se este produto já foi contabilizado
                if product_name not in products_counted:
                    multi_store_total_price += item["price"]
                    products_counted.add(product_name)
                
        multi_store_items_count = len(multi_store_products)
        
        response_parts = []
        
        # Cabeçalho
        response_parts.append("# Resultado da Comparação de Preços\n")
        
        # Produtos não encontrados
        if products_not_found:
            response_parts.append("\n## Produtos não encontrados\n")
            for product in products_not_found:
                response_parts.append(f"- {product}\n")
        
        # Melhor opção em um único supermercado
        response_parts.append(f"\n## Opção 1: Comprar tudo em um só lugar, {single_store_items_count} de {total_requested_items} itens encontrados\n")
        response_parts.append(f"**Supermercado:** {single_store_option.get('supermarket_name', 'Desconhecido')}\n")
        response_parts.append(f"**Preço total:** R$ {single_store_option.get('total_price', 0.0):.2f}\n")
        
        response_parts.append("\n**Itens:**\n")
        for item in single_store_option.get("items", []):
            # Exibir apenas nome do produto e preço
            response_parts.append(f"- {item['product_name']}: R$ {item['price']:.2f}\n")
            # Opcional: Adicionar link/validade se disponível
            valid_until = item.get("valid_until")
            folder_link = item.get("folder_link")
            observations = item.get("observations")
            if valid_until:
                response_parts.append(f"    (Válido até: {valid_until})\n")
            if observations:
                response_parts.append(f"    (Obs: {observations})\n")
            if folder_link:
                response_parts.append(f"    (Mais info: {folder_link})\n")

        # Opção com múltiplos supermercados
        if multi_store_option:
            response_parts.append(f"\n## Opção 2: Comprar em vários lugares, {multi_store_items_count} de {total_requested_items} itens encontrados\n")
            response_parts.append(f"**Preço total:** R$ {multi_store_total_price:.2f}\n")
            if savings > 0:
                response_parts.append(f"**Economia:** R$ {savings:.2f} (aproximadamente {savings_percentage:.1f}%)\n")
            else:
                response_parts.append(f"**%)\n")
            
            for store in multi_store_option:
                store_name = store.get("supermarket_name", "Desconhecido")
                store_total = store.get("total_price", 0.0)
                
                response_parts.append(f"\n**{store_name} (Preço total: R$ {store_total:.2f}):**\n")
                
                for item in store.get("items", []):
                    # Exibir apenas nome do produto e preço
                    response_parts.append(f"- {item['product_name']}: R$ {item['price']:.2f}\n")
                    # Opcional: Adicionar link/validade se disponível
                    valid_until = item.get("valid_until")
                    folder_link = item.get("folder_link")
                    observations = item.get("observations")
                    if valid_until:
                        response_parts.append(f"    (Válido até: {valid_until})\n")
                    if observations:
                        response_parts.append(f"    (Obs: {observations})\n")
                    if folder_link:
                        response_parts.append(f"    (Mais info: {folder_link})\n")
        
        # Conclusão
        response_parts.append("\n## Conclusão\n")
        
        # Verificar se o supermercado único tem todos os itens solicitados
        single_store_complete = single_store_items_count == total_requested_items

        if multi_store_option and savings > 0:
            response_parts.append(f"Comprando cada item onde é mais barato, você economiza R$ {savings:.2f} ({savings_percentage:.1f}%) em comparação com a melhor opção de supermercado único.\n")
            if savings_percentage > 15:
                response_parts.append("**Recomendação: Vale a pena comprar em múltiplos supermercados.**\n")
            else:
                if single_store_complete:
                    response_parts.append("**Recomendação: A economia é pequena, talvez seja mais conveniente comprar em um único supermercado.**\n")
                else:
                    response_parts.append("**Recomendação: A economia é pequena, mas considere que a opção de supermercado único não contém todos os itens solicitados.**\n")
        else:
            if single_store_complete:
                response_parts.append(f"A melhor opção é comprar tudo no **{single_store_option.get('supermarket_name', 'Desconhecido')}**.\n")
            else:
                response_parts.append(f"O **{single_store_option.get('supermarket_name', 'Desconhecido')}** tem o melhor preço para os itens encontrados ({single_store_items_count} de {total_requested_items}), mas não possui todos os itens da sua lista.\n")
        
        formatted_response = "".join(response_parts)
        
        return {
            "recommendation": recommendation,
            "formatted_response": formatted_response,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao formatar resposta: {str(e)}"
        logger.exception(error_message) # Usar exception para logar traceback
        return {
            "recommendation": state.get("recommendation", {}),
            "formatted_response": None,
            "error": error_message
        }

def create_graph() -> StateGraph:
    """
    Cria o grafo de estado para o agente de resposta.
    
    Returns:
        Grafo de estado compilado
    """
    # Criar grafo de estado
    workflow = StateGraph(ResponseState)
    
    # Adicionar nós
    workflow.add_node("format_response", format_response)
    
    # Definir o nó de entrada
    workflow.set_entry_point("format_response")
    
    # Adicionar arestas
    workflow.add_edge("format_response", END)
    
    # Compilar grafo
    return workflow.compile()

def run_response_agent(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de resposta para formatar a recomendação.
    
    Args:
        recommendation: Recomendação de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({
            "recommendation": recommendation,
            "formatted_response": None,
            "error": None
        })
        
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"]
            }
        
        if not result.get("formatted_response"):
            return {
                "success": False,
                "error": "Não foi possível formatar a resposta"
            }
        
        return {
            "success": True,
            "formatted_response": result["formatted_response"]
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de resposta: {str(e)}"
        logger.exception(error_message) # Usar exception para logar traceback
        return {
            "success": False,
            "error": error_message
        }