"""
Agente para refinamento e confirmação de listas de compras.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal
import google.generativeai as genai
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

from storage.operations import BigQueryOperations

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
    ambiguous_items: Optional[Dict[str, List[Dict[str, Any]]]] # Para guardar variantes de itens ambíguos
    packaged_items_info: Optional[Dict[str, Dict[str, Any]]] # Para guardar info de embalagens
    error: Optional[str]

def refine_list_with_db_awareness(state: RefinementState) -> RefinementState:
    """
    Refina a lista de compras usando LLM e consulta ao banco de dados.
    
    Args:
        state: Estado atual
        
    Returns:
        Estado atualizado
    """
    try:
        initial_list = state["initial_list"]
        db_ops = BigQueryOperations()
        
        refined_items = []
        ambiguous_items_details = {}
        packaged_items_info = {}
        
        # 1. Processar cada item da lista inicial
        for item in initial_list.get("items", []):
            product_name = item.get("product_name", "")
            quantity = item.get("quantity", 1.0)
            unit = item.get("unit")
            
            # 2. Verificar embalagem padrão
            package_info = db_ops.get_standard_package_info(product_name)
            if package_info.get("is_packaged") and package_info.get("standard_quantity") and package_info.get("standard_unit") == unit:
                # Se a unidade corresponde e a quantidade é múltiplo da embalagem padrão
                standard_qty = package_info["standard_quantity"]
                if quantity % standard_qty == 0:
                    num_packages = quantity / standard_qty
                    logger.info(f"Produto 	{product_name}	 identificado como embalagem padrão. Quantidade ajustada para {num_packages} pacotes.")
                    item["quantity"] = num_packages
                    item["unit"] = f"pacote(s) de {standard_qty}{unit}" # Atualiza unidade para refletir pacote
                    packaged_items_info[product_name] = package_info
                else:
                    logger.warning(f"Quantidade de 	{product_name}	 ({quantity}{unit}) não é múltiplo da embalagem padrão ({standard_qty}{unit}). Mantendo original.")
            
            # 3. Verificar variantes (ambiguidade)
            # Consideramos ambíguo se o nome for genérico e existirem variantes no DB
            # (Simplificação: verificar se o nome é curto e existem variantes)
            variants = []
            if len(product_name.split()) <= 2: # Heurística simples para nomes genéricos
                variants = db_ops.get_product_variants(product_name)
            
            if len(variants) > 1:
                logger.info(f"Produto 	{product_name}	 é ambíguo. Encontradas {len(variants)} variantes.")
                ambiguous_items_details[product_name] = variants
                # Adiciona o item original à lista refinada por enquanto, será tratado na confirmação
                refined_items.append(item)
            else:
                # Se não for ambíguo, adiciona à lista refinada
                refined_items.append(item)

        # 4. Usar LLM para refinar nomes e corrigir erros (opcional, pode ser redundante)
        # Poderíamos passar a lista `refined_items` para o LLM para correção final, mas
        # a lógica de ambiguidade e pacotes já tratou bastante coisa. Vamos pular por ora.
        refined_list = {"items": refined_items}
        
        logger.info(f"Lista de compras refinada com {len(refined_list.get('items', []))} itens. {len(ambiguous_items_details)} itens ambíguos.")
        
        return {
            "initial_list": initial_list,
            "refined_list": refined_list,
            "ambiguous_items": ambiguous_items_details,
            "packaged_items_info": packaged_items_info,
            "error": None
        }
    except Exception as e:
        error_message = f"Erro ao refinar lista de compras com DB: {str(e)}"
        logger.error(error_message)
        # Em caso de erro, retorna a lista inicial para confirmação
        return {
            "initial_list": state["initial_list"],
            "refined_list": state["initial_list"], 
            "ambiguous_items": {},
            "packaged_items_info": {},
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
    workflow.add_node("refine_list", refine_list_with_db_awareness)
    
    # Definir o nó de entrada
    workflow.set_entry_point("refine_list")
    
    # Adicionar arestas
    workflow.add_edge("refine_list", END)
    
    # Compilar grafo
    return workflow.compile()

def run_refinement_agent(initial_list: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executa o agente de refinamento para corrigir, normalizar e identificar ambiguidades.
    
    Args:
        initial_list: Lista de compras inicial extraída
        
    Returns:
        Dicionário com resultado da operação (contendo a lista refinada e informações de ambiguidade/pacotes)
    """
    try:
        # Criar grafo
        graph = create_graph()
        
        # Executar grafo
        result = graph.invoke({
            "initial_list": initial_list,
            "refined_list": None,
            "ambiguous_items": None,
            "packaged_items_info": None,
            "error": None
        })
        
        # Mesmo se houver erro no refinamento, retornamos a lista (inicial ou refinada)
        # O erro será logado, mas o fluxo principal pode continuar para confirmação
        return {
            "success": True,
            "refined_list": result.get("refined_list", initial_list), # Retorna a refinada ou a inicial
            "ambiguous_items": result.get("ambiguous_items", {}),
            "packaged_items_info": result.get("packaged_items_info", {}),
            "refinement_error": result.get("error") # Informa se houve erro no refinamento
        }
    except Exception as e:
        error_message = f"Erro ao executar agente de refinamento: {str(e)}"
        logger.error(error_message)
        # Em caso de falha total, retorna a lista inicial
        return {
            "success": False, 
            "refined_list": initial_list,
            "ambiguous_items": {},
            "packaged_items_info": {},
            "error": error_message
        }

