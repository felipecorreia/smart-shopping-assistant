"""
Agente de compreensão - Versão final corrigida
"""

import logging
from typing import Dict, Any, Optional
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph, END
from pydantic import BaseModel

from llm.gemini_client import GeminiClient
from data.models import ShoppingItem, ShoppingList

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class UnderstandingState(BaseModel):
    """Estado do agente de compreensão."""
    input_text: str = ""
    shopping_list: Optional[ShoppingList] = None
    error: Optional[str] = None

def parse_shopping_list(state: UnderstandingState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    """Analisa a lista de compras em linguagem natural."""
    try:
        gemini_client = GeminiClient()
        items_data = gemini_client.parse_shopping_list(state.input_text)
        
        items = [
            ShoppingItem(
                product_name=item_data["product_name"],
                quantity=item_data.get("quantity", 1.0),
                unit=item_data.get("unit", "un")
            )
            for item_data in items_data
        ]
        
        shopping_list = ShoppingList(items=items)
        logger.info(f"Lista de compras analisada com sucesso: {len(items)} itens")
        
        return {
            "input_text": state.input_text,
            "shopping_list": shopping_list,
            "error": None
        }
    except Exception as e:
        logger.error(f"Erro ao analisar lista: {str(e)}")
        return {
            "input_text": state.input_text,
            "shopping_list": None,
            "error": f"Erro ao analisar lista: {str(e)}"
        }

def should_retry(state: UnderstandingState) -> str:
    """Determina se deve tentar novamente."""
    if state.error and "Erro ao analisar lista" in state.error:
        return "retry"
    return "end"

def create_understanding_agent() -> StateGraph:
    """Cria o grafo do agente de compreensão."""
    workflow = StateGraph(UnderstandingState)
    workflow.add_node("parse", parse_shopping_list)
    workflow.add_conditional_edges(
        "parse",
        should_retry,
        {"retry": "parse", "end": END}
    )
    workflow.set_entry_point("parse")
    return workflow.compile()

def run_understanding_agent(text: str) -> Dict[str, Any]:
    """Executa o agente e retorna resultado padronizado."""
    try:
        agent = create_understanding_agent()
        result = agent.invoke(UnderstandingState(input_text=text))
        
        # Converter para UnderstandingState se necessário
        if not isinstance(result, UnderstandingState):
            result = UnderstandingState(**result)
        
        # Converter ShoppingList para dicionário
        items = []
        if result.shopping_list and result.shopping_list.items:
            items = [
                {
                    "product_name": item.product_name,
                    "quantity": item.quantity,
                    "unit": item.unit
                }
                for item in result.shopping_list.items
            ]
        
        return {
            "success": True,
            "shopping_list": {"items": items},
            "error": result.error
        }
    except Exception as e:
        logger.error(f"Erro no agente: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao processar lista: {str(e)}",
            "shopping_list": {"items": []}
        }