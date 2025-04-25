"""
Agente para formatação de respostas.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from llm.gemini_client import GeminiClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def format_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Formata a resposta para o usuário.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        recommendation = state.get("recommendation", {})
        
        if not recommendation:
            state["success"] = False
            state["error"] = "Recomendação não encontrada"
            return state
        
        # Inicializar cliente Gemini
        client = GeminiClient()
        
        # Formatar resposta
        formatted_response = client.format_shopping_recommendation(recommendation)
        
        # Atualizar estado
        state["formatted_response"] = formatted_response
        state["success"] = True
        
        logger.info("Resposta formatada com sucesso")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao formatar resposta: {str(e)}")
        state["success"] = False
        state["error"] = f"Erro ao formatar resposta: {str(e)}"
        return state

def create_response_graph() -> StateGraph:
    """
    Cria o grafo de resposta.
    
    Returns:
        Grafo de resposta
    """
    # Definir grafo
    workflow = StateGraph(name="response")
    
    # Adicionar nós
    workflow.add_node("format_response", format_response)
    
    # Definir arestas
    workflow.set_entry_point("format_response")
    workflow.add_edge("format_response", END)
    
    # Compilar grafo
    return workflow.compile()

def run_response_agent(recommendation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de resposta.
    
    Args:
        recommendation: Recomendação de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_response_graph()
        
        # Executar grafo
        result = graph.invoke({"recommendation": recommendation})
        
        if result.get("success", False):
            logger.info("Agente de resposta executado com sucesso")
            return result
        else:
            logger.error(f"Erro no agente de resposta: {result.get('error')}")
            return result
    
    except Exception as e:
        logger.error(f"Erro ao executar agente de resposta: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao executar agente de resposta: {str(e)}"
        }
