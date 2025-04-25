"""
Agente para compreensão de listas de compras em linguagem natural.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import json

from llm.gemini_client import GeminiClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def parse_shopping_list(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analisa uma lista de compras em linguagem natural.
    
    Args:
        state: Estado atual do grafo
        
    Returns:
        Estado atualizado
    """
    try:
        text = state.get("text", "")
        
        # Inicializar cliente Gemini
        client = GeminiClient()
        
        # Analisar lista de compras
        items = client.parse_shopping_list(text)
        
        # Atualizar estado
        state["shopping_list"] = {"items": items}
        state["success"] = True
        
        logger.info(f"Lista de compras analisada com sucesso: {len(items)} itens")
        return state
    
    except Exception as e:
        logger.error(f"Erro ao analisar lista de compras: {str(e)}")
        state["success"] = False
        state["error"] = f"Erro ao analisar lista de compras: {str(e)}"
        return state

def create_understanding_graph() -> StateGraph:
    """
    Cria o grafo de compreensão.
    
    Returns:
        Grafo de compreensão
    """
    # Definir grafo
    workflow = StateGraph(name="understanding")
    
    # Adicionar nós
    workflow.add_node("parse_shopping_list", parse_shopping_list)
    
    # Definir arestas
    workflow.set_entry_point("parse_shopping_list")
    workflow.add_edge("parse_shopping_list", END)
    
    # Compilar grafo
    return workflow.compile()

def run_understanding_agent(text: str) -> Dict[str, Any]:
    """
    Executa o agente de compreensão.
    
    Args:
        text: Texto da lista de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_understanding_graph()
        
        # Executar grafo
        result = graph.invoke({"text": text})
        
        if result.get("success", False):
            logger.info("Agente de compreensão executado com sucesso")
            return result
        else:
            logger.error(f"Erro no agente de compreensão: {result.get('error')}")
            return result
    
    except Exception as e:
        logger.error(f"Erro ao executar agente de compreensão: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao executar agente de compreensão: {str(e)}"
        }
