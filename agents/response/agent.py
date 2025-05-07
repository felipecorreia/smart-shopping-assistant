"""
Agente para formatação de resposta (versão simplificada sem cálculo de quantidades).
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal, Tuple
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

def classificar_cenario(total_itens: int, itens_encontrados: int, encontrados_por_mercado: Dict[str, int], 
                        preco_centralizado: float, preco_distribuido: float, 
                        nome_mercado_centralizado: str) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Classifica o cenário de compra e fornece recomendação personalizada.
    
    Args:
        total_itens: Total de itens solicitados pelo usuário
        itens_encontrados: Total de itens encontrados (únicos) em todos os mercados
        encontrados_por_mercado: Dicionário {nome_mercado: num_itens_encontrados}
        preco_centralizado: Preço total da opção em um único mercado
        preco_distribuido: Preço total da opção distribuída em vários mercados
        nome_mercado_centralizado: Nome do mercado da opção centralizada
        
    Returns:
        tuple: (cenario, justificativa, recomendacao, detalhes_adicionais)
    """
    # Verificar se algum item foi encontrado
    if itens_encontrados == 0:
        return "r0", "Nenhum item encontrado", "Tente outros termos de busca ou verifique a disponibilidade em outros mercados.", {}
    
    # Se não encontrou todos os itens, verificar distribuição
    max_itens_mercado = max(encontrados_por_mercado.values()) if encontrados_por_mercado else 0
    mercado_max_itens = [m for m, n in encontrados_por_mercado.items() if n == max_itens_mercado]
    mercado_completo = [m for m, n in encontrados_por_mercado.items() if n == total_itens]
    
    # Calcular diferença de preço e porcentagem
    diferenca = abs(preco_centralizado - preco_distribuido)
    percentual = (diferenca / preco_centralizado * 100) if preco_centralizado > 0 else 0
    
    detalhes = {
        "diferenca_valor": diferenca,
        "diferenca_percentual": percentual,
        "mercado_central": nome_mercado_centralizado,
        "max_itens_mercado": max_itens_mercado,
        "total_encontrados": itens_encontrados
    }
    
    # Cenários onde nenhum mercado tem todos os itens
    if not mercado_completo:
        # Cenário r1: Muito disperso (cada mercado tem poucos itens)
        if max_itens_mercado <= total_itens * 0.3:  # 30% ou menos dos itens em qualquer mercado
            return "r1", "Produtos muito dispersos entre mercados", "Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, a recomendação é comprar em vários mercados para obter mais itens da sua lista.", detalhes
        
        # Cenário r2: Moderadamente disperso
        elif max_itens_mercado <= total_itens * 0.7:  # Entre 30% e 70% dos itens no melhor mercado
            return "r2", "Produtos moderadamente dispersos", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, a recomendação é comprar principalmente no {mercado_max_itens[0]} e complementar nos demais.", detalhes
        
        # Cenário r3/r4: Quase todos em um único mercado
        elif max_itens_mercado >= total_itens * 0.7:  # 70% ou mais dos itens no melhor mercado
            if preco_centralizado <= preco_distribuido:
                return "r3", f"Quase todos os itens disponíveis no {nome_mercado_centralizado}", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, a recomendação é comprar tudo no {nome_mercado_centralizado}, pois é mais econômico.", detalhes
            else:
                # Avaliar se vale a pena distribuir com base no percentual
                if percentual > 10:  # Economia significativa
                    return "r4", f"Quase todos no {nome_mercado_centralizado}, mas dividir é mais barato", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, vale a pena dividir a compra para economizar R$ {diferenca:.2f} ({percentual:.1f}%).", detalhes
                else:
                    return "r4", f"Quase todos no {nome_mercado_centralizado}", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. A diferença de R$ {diferenca:.2f} talvez não compense o esforço de dividir a compra.", detalhes
        
        # Cenário r5: Nenhum mercado tem todos, e nenhum tem a maioria
        else:
            return "r5", "Nenhum mercado tem todos os itens", "Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, é necessário dividir suas compras entre mercados.", detalhes
    
    # Cenários onde pelo menos um mercado tem todos os itens
    else:
        # Cenário r8: Preços iguais
        if abs(preco_centralizado - preco_distribuido) < 0.01:
            return "r8", "Preços praticamente iguais entre as opções", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, escolha o mercado mais conveniente para você. O {nome_mercado_centralizado} tem todos os itens.", detalhes
        
        # Cenário r6: Um mercado tem todos por menor preço
        if preco_centralizado < preco_distribuido:
            return "r6", f"O {nome_mercado_centralizado} tem todos os itens pelo menor preço", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, compre tudo no {nome_mercado_centralizado} e economize R$ {diferenca:.2f}.", detalhes
        
        # Cenário r7: Distribuir é mais barato
        else:
            if percentual <= 5:  # Diferença pequena
                return "r7", "Diferença pequena de preço", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, comprar tudo no {nome_mercado_centralizado} é mais prático. A diferença é apenas R$ {diferenca:.2f}.", detalhes
            else:
                return "r7b", "Distribuir é significativamente mais barato", f"Analisamos nos folders de promoção quais mercados possuem mais itens e qual a combinação é mais barata. Sendo assim, vale a pena dividir suas compras para economizar R$ {diferenca:.2f} ({percentual:.1f}%).", detalhes

def format_response(state: ResponseState) -> ResponseState:
    """
    Formata a resposta para o usuário com recomendação baseada na classificação de cenário.
    
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
        total_requested_items = recommendation.get("total_requested_items", 0)  # Total de itens solicitados
        
        # Calcular itens encontrados em cada opção
        single_store_items = single_store_option.get("items", [])
        single_store_items_count = len(single_store_items)
        single_store_name = single_store_option.get("supermarket_name", "Desconhecido")
        single_store_price = single_store_option.get("total_price", 0.0)
        
        # Para a opção multi_store, contar produtos únicos e calcular preço total
        multi_store_products = set()
        multi_store_total_price = 0.0
        products_counted = set()
        encontrados_por_mercado = {}
        
        for store in multi_store_option:
            store_name = store.get("supermarket_name", "Desconhecido")
            store_items = store.get("items", [])
            encontrados_por_mercado[store_name] = len(store_items)
            
            for item in store_items:
                product_name = item.get("product_name")
                multi_store_products.add(product_name)
                
                # Verificar se este produto já foi contabilizado
                if product_name not in products_counted:
                    multi_store_total_price += item["price"]
                    products_counted.add(product_name)
                
        multi_store_items_count = len(multi_store_products)
        total_items_found = len(set(p.get("product_name") for p in single_store_items).union(multi_store_products))
        
        # Classificar o cenário
        cenario, justificativa, recomendacao, detalhes = classificar_cenario(
            total_requested_items, 
            total_items_found,
            encontrados_por_mercado, 
            single_store_price, 
            multi_store_total_price,
            single_store_name
        )
        
        # Determinar qual opção é recomendada
        opcao_recomendada = "2"  # Default para multi_store
        if cenario in ["r3", "r6", "r7"]:
            opcao_recomendada = "1"  # Para cenários onde o único mercado é recomendado
        
        response_parts = []
        
        # Cabeçalho
        response_parts.append("# Resumo da Comparação de Preços\n")
        
        # Informações gerais
        response_parts.append(f"**Itens solicitados:** {total_requested_items}\n")
        response_parts.append(f"**Itens encontrados:** {total_items_found}\n")
        
        # Produtos não encontrados
        if products_not_found:
            response_parts.append("\n## Produtos não encontrados\n")
            for product in products_not_found:
                response_parts.append(f"- {product}\n")
        
        # Opções de compra - Novo formato
        response_parts.append("\n## Separei 2 opções para você economizar na sua lista de compras:\n")
        
        # Opção 1: Mercado único - Formato melhorado
        response_parts.append(f"\n### Opção 1: Comprar a maior parte da lista em um só lugar ({single_store_items_count} de {total_requested_items} itens)\n")
        response_parts.append(f"**Mercado:** {single_store_name}\n")
        response_parts.append(f"**Preço total:** R$ {single_store_price:.2f}\n")
        
        # Produtos e preços da Opção 1
        response_parts.append("\n**Produtos e preços:**\n")
        for item in single_store_items:
            product_name = item.get("product_name", "")
            price = item.get("price", 0.0)
            response_parts.append(f"- {product_name}: R$ {price:.2f}\n")
        
        # Link do folder da Opção 1
        folder_link = None
        if single_store_items and single_store_items[0].get("folder_link"):
            folder_link = single_store_items[0].get("folder_link")
            response_parts.append(f"\n**Link do folder:** {folder_link}\n")
        
        # Opção 2: Múltiplos mercados - Formato melhorado
        if multi_store_option:
            response_parts.append(f"\n### Opção 2: Dividir a compra em diversos mercados ({multi_store_items_count} de {total_requested_items} itens)\n")
            response_parts.append(f"**Sua compra total será:** R$ {multi_store_total_price:.2f}\n")
            
            # Detalhar cada mercado separadamente
            for store in multi_store_option:
                store_name = store.get("supermarket_name", "Desconhecido")
                store_total = store.get("total_price", 0.0)
                store_items = store.get("items", [])
                
                response_parts.append(f"\n**{store_name}** ({len(store_items)} itens)\n")
                response_parts.append(f"**Total da compra:** R$ {store_total:.2f}\n")
                
                # Listar produtos deste mercado
                response_parts.append("**Produtos e preços:**\n")
                for item in store_items:
                    product_name = item.get("product_name", "")
                    price = item.get("price", 0.0)
                    response_parts.append(f"- {product_name}: R$ {price:.2f}\n")
                
                # Link do folder deste mercado
                if store_items and store_items[0].get("folder_link"):
                    folder_link = store_items[0].get("folder_link")
                    response_parts.append(f"**Link do folder:** {folder_link}\n")
        
        # Recomendação (nova seção com formato melhorado)
        response_parts.append(f"\n## Nossa Recomendação (Opção {opcao_recomendada})\n")
        response_parts.append(f"**Análise:** {justificativa}\n")
        response_parts.append(f"**Recomendamos:** {recomendacao}\n")
        
        formatted_response = "".join(response_parts)
        
        return {
            "recommendation": recommendation,
            "formatted_response": formatted_response,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao formatar resposta: {str(e)}"
        logger.exception(error_message)
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
        logger.exception(error_message)
        return {
            "success": False,
            "error": error_message
        }