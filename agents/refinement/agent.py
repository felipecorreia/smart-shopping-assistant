"""
Agente para refinamento e confirmação de listas de compras.
"""

import os
import logging
from typing import Dict, Any, List, Optional, TypedDict, Annotated, Literal, Tuple
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
    spelling_corrections: Optional[Dict[str, Dict[str, Any]]] # Para rastrear correções ortográficas
    error: Optional[str]

def correct_product_spelling(product_name: str, db_ops: BigQueryOperations) -> Tuple[str, float, bool]:
    """
    Corrige erros ortográficos em nomes de produtos usando LLM e verificação no banco de dados.
    
    Args:
        product_name: Nome do produto com possível erro ortográfico
        db_ops: Operações de banco de dados
        
    Returns:
        Tupla com (nome_corrigido, confiança, é_correção)
    """
    # Se o nome já estiver no banco, não precisa corrigir
    if db_ops.product_exists(product_name):
        return product_name, 1.0, False
    
    # Verificar produtos similares no banco
    similar_products = db_ops.get_similar_products(product_name, threshold=0.7)
    
    # Se encontrou produtos similares, usar o LLM para decidir qual é o mais provável
    if similar_products:
        # Usar LLM para escolher a melhor opção
        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"temperature": 0.2}
        )
        
        prompt = f"""
        Corrija o possível erro ortográfico no nome de produto: "{product_name}"
        
        Possíveis produtos corretos no banco de dados:
        {", ".join([p["name"] for p in similar_products])}
        
        Forneça apenas o nome correto, sem explicações adicionais. Se não tiver certeza ou o nome original estiver correto, retorne o nome original.
        """
        
        response = model.generate_content(prompt)
        corrected_name = response.text.strip()
        
        # Verificar confiança na correção (comparando com as opções)
        for product in similar_products:
            if product["name"].lower() == corrected_name.lower():
                # Calcular confiança baseada na similitude
                confidence = product.get("similarity", 0.8)
                return corrected_name, confidence, (corrected_name.lower() != product_name.lower())
        
        # Se o LLM retornou o nome original ou algo fora da lista
        return product_name, 0.5, False
    
    # Caso não tenha encontrado similares no banco, tentar correção direta com LLM
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        generation_config={"temperature": 0.1}
    )
    
    prompt = f"""
    Verifique se o seguinte nome de produto em português brasileiro possui erro ortográfico: "{product_name}"
    
    Se houver erro, corrija e retorne apenas o nome corrigido.
    Se não houver erro ou se não tiver certeza, retorne exatamente o nome original.
    
    Responda apenas com o nome corrigido ou original, sem explicações adicionais.
    """
    
    response = model.generate_content(prompt)
    corrected_name = response.text.strip()
    
    # Determinar se houve correção e confiança
    is_correction = (corrected_name.lower() != product_name.lower())
    confidence = 0.85 if is_correction else 1.0  # Confiança alta se o LLM fez correção
    
    return corrected_name, confidence, is_correction

def refine_list_with_db_awareness(state: RefinementState) -> RefinementState:
    """
    Refina a lista de compras usando LLM e consulta ao banco de dados.
    Inclui correção ortográfica para nomes de produtos.
    
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
        spelling_corrections = {}  # Para rastrear correções ortográficas
        
        # 1. Processar cada item da lista inicial
        for item in initial_list.get("items", []):
            product_name = item.get("product_name", "")
            quantity = item.get("quantity", 1.0)
            unit = item.get("unit")
            
            # 1.1 Corrigir ortografia do nome do produto
            corrected_name, confidence, is_correction = correct_product_spelling(product_name, db_ops)
            
            if is_correction and confidence >= 0.7:  # Limiar de confiança para aplicar correção
                logger.info(f"Correção ortográfica: '{product_name}' -> '{corrected_name}' (confiança: {confidence:.2f})")
                # Guardar informação sobre a correção
                spelling_corrections[product_name] = {
                    "original": product_name,
                    "corrected": corrected_name,
                    "confidence": confidence
                }
                # Atualizar o nome do produto
                product_name = corrected_name
                item["product_name"] = corrected_name
            
            # 2. Verificar embalagem padrão
            package_info = db_ops.get_standard_package_info(product_name)
            if package_info.get("is_packaged") and package_info.get("standard_quantity") and package_info.get("standard_unit") == unit:
                # Se a unidade corresponde e a quantidade é múltiplo da embalagem padrão
                standard_qty = package_info["standard_quantity"]
                if quantity % standard_qty == 0:
                    num_packages = quantity / standard_qty
                    logger.info(f"Produto \t{product_name}\t identificado como embalagem padrão. Quantidade ajustada para {num_packages} pacotes.")
                    item["quantity"] = num_packages
                    item["unit"] = f"pacote(s) de {standard_qty}{unit}" # Atualiza unidade para refletir pacote
                    packaged_items_info[product_name] = package_info
                else:
                    logger.warning(f"Quantidade de \t{product_name}\t ({quantity}{unit}) não é múltiplo da embalagem padrão ({standard_qty}{unit}). Mantendo original.")
            
            # 3. Verificar variantes (ambiguidade)
            # Consideramos ambíguo se o nome for genérico e existirem variantes no DB
            # (Simplificação: verificar se o nome é curto e existem variantes)
            variants = []
            if len(product_name.split()) <= 2: # Heurística simples para nomes genéricos
                variants = db_ops.get_product_variants(product_name)
            
            if len(variants) > 1:
                logger.info(f"Produto \t{product_name}\t é ambíguo. Encontradas {len(variants)} variantes.")
                ambiguous_items_details[product_name] = variants
                # Adiciona o item original à lista refinada por enquanto, será tratado na confirmação
                refined_items.append(item)
            else:
                # Se não for ambíguo, adiciona à lista refinada
                refined_items.append(item)

        # 4. Usar LLM para refinamento final de consistência (opcional)
        # Para casos complexos que a lógica acima não pegou
        
        refined_list = {"items": refined_items}
        
        logger.info(f"Lista de compras refinada com {len(refined_list.get('items', []))} itens. "
                   f"{len(ambiguous_items_details)} itens ambíguos. "
                   f"{len(spelling_corrections)} correções ortográficas.")
        
        return {
            "initial_list": initial_list,
            "refined_list": refined_list,
            "ambiguous_items": ambiguous_items_details,
            "packaged_items_info": packaged_items_info,
            "spelling_corrections": spelling_corrections,
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
            "spelling_corrections": {},
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
            "spelling_corrections": None,
            "error": None
        })
        
        # Mesmo se houver erro no refinamento, retornamos a lista (inicial ou refinada)
        # O erro será logado, mas o fluxo principal pode continuar para confirmação
        return {
            "success": True,
            "refined_list": result.get("refined_list", initial_list), # Retorna a refinada ou a inicial
            "ambiguous_items": result.get("ambiguous_items", {}),
            "packaged_items_info": result.get("packaged_items_info", {}),
            "spelling_corrections": result.get("spelling_corrections", {}),
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
            "spelling_corrections": {},
            "error": error_message
        }