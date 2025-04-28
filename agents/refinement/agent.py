"""
Agente para refinamento e confirmação de listas de compras.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
import google.generativeai as genai
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

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
class RefinementState(TypedDict):
    """Estado do agente de refinamento."""
    initial_list: Dict[str, Any]
    refined_list: Optional[Dict[str, Any]]
    error: Optional[str]

def refine_list(state: RefinementState) -> RefinementState:
    """
    Refina a lista de compras usando LLM para correções e normalização.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        initial_list = state["initial_list"]
        
        if not api_key:
            raise ValueError("API key do Gemini não configurada")
        
        # Usar Gemini para refinar a lista
        model = genai.GenerativeModel(model_name='gemini-2.0-flash') # Ou o modelo que você está usando
        
        # Converter lista inicial para texto para o prompt
        import json
        initial_list_json = json.dumps(initial_list, indent=2, ensure_ascii=False)
        
        prompt = f"""
        Revise a seguinte lista de compras extraída de um texto:
        
        ```json
        {initial_list_json}
        ```
        
        Tarefas:
        1. Corrija quaisquer erros de português nos nomes dos produtos.
        2. Normalize os nomes dos produtos para serem mais genéricos e fáceis de encontrar (ex: "Arroz Tio João 5kg" -> "Arroz", "Coca-Cola 2L" -> "Refrigerante Cola"). Mantenha a quantidade e unidade originais.
        3. Verifique se as quantidades e unidades parecem razoáveis.
        
        Retorne apenas um objeto JSON com a lista refinada no mesmo formato original:
        {{
            "items": [
                {{
                    "product_name": "nome do produto refinado",
                    "quantity": quantidade,
                    "unit": "unidade"
                }},
                ...
            ]
        }}
        
        Não inclua nenhum texto adicional, apenas o JSON.
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
        refined_list = json.loads(json_text)
        
        logger.info(f"Lista de compras refinada com {len(refined_list.get('items', []))} itens")
        
        return {
            "initial_list": initial_list,
            "refined_list": refined_list,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao refinar lista de compras: {str(e)}"
        logger.error(error_message)
        # Em caso de erro, retorna a lista inicial para confirmação
        return {
            "initial_list": state["initial_list"],
            "refined_list": state["initial_list"], 
            "error": error_message # Mantém o erro para log, mas permite confirmação
        }

def create_graph() -> StateGraph:
    """
    Cria o grafo de estado para o agente de refinamento.
    
    Returns:
        Grafo de estado compilado
    """
    # Criar grafo de estado
    workflow = StateGraph(RefinementState)
    
    # Adicionar nós
    workflow.add_node("refine_list", refine_list)
    
    # Definir o nó de entrada
    workflow.set_entry_point("refine_list")
    
    # Adicionar arestas
    workflow.add_edge("refine_list", END)
    
    # Compilar grafo
    return workflow.compile()

def run_refinement_agent(initial_list: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de refinamento para corrigir e normalizar uma lista de compras.
    
    Args:
        initial_list: Lista de compras inicial extraída
        
    Returns:
        Dicionário com resultado da operação (contendo a lista refinada)
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({
            "initial_list": initial_list,
            "refined_list": None,
            "error": None
        })
        
        # Mesmo se houver erro no refinamento, retornamos a lista (inicial ou refinada)
        # O erro será logado, mas o fluxo principal pode continuar para confirmação
        return {
            "success": True,
            "refined_list": result.get("refined_list", initial_list), # Retorna a refinada ou a inicial
            "refinement_error": result.get("error") # Informa se houve erro no refinamento
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de refinamento: {str(e)}"
        logger.error(error_message)
        # Em caso de falha total, retorna a lista inicial
        return {
            "success": False, 
            "refined_list": initial_list,
            "error": error_message
        }
