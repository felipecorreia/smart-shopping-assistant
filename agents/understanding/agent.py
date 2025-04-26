"""
Agente para compreensão de listas de compras em linguagem natural.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
import google.generativeai as genai
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

# Configurar Gemini
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    logger.error("API key do Gemini não encontrada. Configure a variável GEMINI_API_KEY no arquivo .env")
else:
    genai.configure(api_key=api_key)

# Definir o schema de estado
class UnderstandingState(TypedDict):
    """Estado do agente de compreensão."""
    input: str
    shopping_list: Optional[Dict[str, Any]]
    error: Optional[str]

def parse_input(state: UnderstandingState) -> UnderstandingState:
    """
    Analisa o texto de entrada para identificar a intenção do usuário.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        input_text = state["input"]
        logger.info(f"Analisando texto de entrada: {input_text}")
        
        # Estado atualizado
        return {
            "input": input_text,
            "shopping_list": None,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao analisar texto de entrada: {str(e)}"
        logger.error(error_message)
        return {
            "input": state["input"],
            "shopping_list": None,
            "error": error_message
        }

def extract_items(state: UnderstandingState) -> UnderstandingState:
    """
    Extrai itens da lista de compras do texto de entrada.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        input_text = state["input"]
        
        if not api_key:
            raise ValueError("API key do Gemini não configurada")
        
        # Usar Gemini para extrair itens da lista de compras
        model = genai.GenerativeModel('gemini-2.0-flash')
        prompt = f"""
        Extraia os itens da lista de compras do seguinte texto:
        
        "{input_text}"
        
        Retorne apenas um objeto JSON com o seguinte formato:
        {{
            "items": [
                {{
                    "product_name": "nome do produto",
                    "quantity": quantidade (número),
                    "unit": "unidade (kg, l, un, etc.)"
                }},
                ...
            ]
        }}
        
        Regras:
        1. Se a quantidade não for especificada, use 1.0
        2. Se a unidade não for especificada, deixe como null
        3. Normalize os nomes dos produtos (ex: "1kg de arroz" -> "arroz" com quantidade=1.0 e unit="kg")
        4. Não inclua nenhum texto adicional, apenas o JSON
        """
        
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Limpar a resposta para garantir que é um JSON válido
        json_text = response_text.strip()
        if json_text.startswith("```json"):
            json_text = json_text[7:]
        if json_text.endswith("```"):
            json_text = json_text[:-3]
        
        json_text = json_text.strip()
        
        # Converter para dicionário
        import json
        shopping_list = json.loads(json_text)
        
        logger.info(f"Extraídos {len(shopping_list.get('items', []))} itens da lista de compras")
        
        return {
            "input": input_text,
            "shopping_list": shopping_list,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao extrair itens da lista de compras: {str(e)}"
        logger.error(error_message)
        return {
            "input": input_text,
            "shopping_list": None,
            "error": error_message
        }

def should_end(state: UnderstandingState) -> Literal["extract_items", "end"]:
    """
    Determina se o fluxo deve continuar ou terminar.
    
    Args:
        state: Estado atual
        
    Returns:
        Nome do próximo nó ou "end"
    """
    if state.get("error"):
        return "end"
    
    if state.get("shopping_list") is None:
        return "extract_items"
    
    return "end"

def create_graph() -> StateGraph:
    """
    Cria o grafo de estado para o agente de compreensão.
    
    Returns:
        Grafo de estado compilado
    """
    # Criar grafo de estado
    workflow = StateGraph(UnderstandingState)
    
    # Adicionar nós
    workflow.add_node("parse_input", parse_input)
    workflow.add_node("extract_items", extract_items)
    
    # Definir o nó de entrada
    workflow.set_entry_point("parse_input")
    
    # Adicionar arestas
    workflow.add_conditional_edges(
        "parse_input",
        should_end,
        {
            "extract_items": "extract_items",
            "end": END
        }
    )
    
    workflow.add_edge("extract_items", END)
    
    # Compilar grafo
    return workflow.compile()

def run_understanding_agent(text: str) -> Dict[str, Any]:
    """
    Executa o agente de compreensão para processar uma lista de compras.
    
    Args:
        text: Texto da lista de compras
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({"input": text})
        
        if result.get("error"):
            return {
                "success": False,
                "error": result["error"]
            }
        
        return {
            "success": True,
            "shopping_list": result.get("shopping_list", {})
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de compreensão: {str(e)}"
        logger.error(error_message)
        return {
            "success": False,
            "error": error_message
        }
