"""
Agente para formatação de respostas.
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
class ResponseState(TypedDict):
    """Estado do agente de resposta."""
    recommendation: Dict[str, Any]
    formatted_response: Optional[str]
    error: Optional[str]

def format_response(state: ResponseState) -> ResponseState:
    """
    Formata a resposta para o usuário.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        recommendation = state["recommendation"]
        
        if not api_key:
            # Formatação básica sem LLM
            single_store = recommendation["single_store_option"]
            multi_store = recommendation["multi_store_option"]
            savings = recommendation["savings"]
            savings_percentage = recommendation["savings_percentage"]
            products_not_found = recommendation["products_not_found"]
            
            response_parts = []
            
            # Adicionar cabeçalho
            response_parts.append("# Análise da sua lista de compras\n")
            
            # Adicionar produtos não encontrados
            if products_not_found:
                response_parts.append("## Produtos não encontrados\n")
                for product in products_not_found:
                    response_parts.append(f"- {product}\n")
                response_parts.append("\n")
            
            # Adicionar opção de único supermercado
            response_parts.append(f"## Opção em um único supermercado: {single_store['supermarket_name']}\n")
            response_parts.append(f"**Preço total: R$ {single_store['total_price']:.2f}**\n\n")
            
            for item in single_store["items"]:
                response_parts.append(f"- {item['product_name']}: R$ {item['price']:.2f}\n")
            
            response_parts.append("\n")
            
            # Adicionar opção de múltiplos supermercados
            if multi_store and savings > 0:
                response_parts.append(f"## Opção em múltiplos supermercados\n")
                response_parts.append(f"**Preço total: R$ {single_store['total_price'] - savings:.2f}**\n")
                response_parts.append(f"**Economia: R$ {savings:.2f} ({savings_percentage:.2f}%)**\n\n")
                
                for store in multi_store:
                    response_parts.append(f"### {store['supermarket_name']} - R$ {store['total_price']:.2f}\n")
                    for item in store["items"]:
                        response_parts.append(f"- {item['product_name']}: R$ {item['price']:.2f}\n")
                    response_parts.append("\n")
            
            # Adicionar recomendação
            response_parts.append("## Recomendação\n")
            if multi_store and savings > 0:
                response_parts.append(f"Recomendamos comprar em múltiplos supermercados para economizar R$ {savings:.2f} ({savings_percentage:.2f}%).\n")
            else:
                response_parts.append(f"Recomendamos comprar tudo no {single_store['supermarket_name']}.\n")
            
            formatted_response = "".join(response_parts)
        else:
            # Usar Gemini para formatar resposta
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            # Converter recomendação para texto
            import json
            recommendation_json = json.dumps(recommendation, indent=2)
            
            prompt = f"""
            Formate uma resposta amigável para o usuário com base na seguinte recomendação de compras:
            
            ```json
            {recommendation_json}
            ```
            
            A resposta deve incluir:
            1. Uma saudação amigável
            2. Lista de produtos não encontrados (se houver)
            3. Opção de compra em um único supermercado, com nome do mercado, preço total e lista de produtos com preços
            4. Opção de compra em múltiplos supermercados (se economizar dinheiro), com nome dos mercados, preço total, economia e lista de produtos com preços para cada mercado
            5. Uma recomendação clara sobre qual opção é melhor
            
            Use formatação Markdown para tornar a resposta mais legível.
            """
            
            response = model.generate_content(prompt)
            formatted_response = response.text
        
        logger.info("Resposta formatada com sucesso")
        
        return {
            "recommendation": recommendation,
            "formatted_response": formatted_response,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao formatar resposta: {str(e)}"
        logger.error(error_message)
        return {
            "recommendation": state["recommendation"],
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
    Executa o agente de resposta para formatar uma recomendação.
    
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
        logger.error(error_message)
        return {
            "success": False,
            "error": error_message
        }
