"""
Gerenciamento de estados para conversas do Bot do Telegram.
"""

import re
import logging
from typing import Dict, Any, List

from telegram.ext import ContextTypes

# Configurar logging
logger = logging.getLogger(__name__)

def initialize_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Inicializa o estado do usuário, se necessário.
    
    Args:
        context: Contexto da conversa
    """
    if not context.user_data:
        # Não substituimos o objeto user_data, apenas manipulamos seu conteúdo
        context.user_data.clear()
        context.user_data.update({
            "refined_list": {"items": []},
            "ambiguous_items": {},
            "corrections": {},
            "current_ambiguous_items": [],
            "waiting_for_input": None
        })

def get_current_state(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """
    Obtém o estado atual do usuário.
    
    Args:
        context: Contexto da conversa
        
    Returns:
        Estado atual
    """
    # Garantir que o estado está inicializado
    if not context.user_data:
        initialize_state(context)
    
    return context.user_data

def update_state(context: ContextTypes.DEFAULT_TYPE, updates: Dict[str, Any]) -> None:
    """
    Atualiza o estado do usuário.
    
    Args:
        context: Contexto da conversa
        updates: Atualizações a serem aplicadas
    """
    # Garantir que o estado está inicializado
    if not context.user_data:
        initialize_state(context)
    
    # Aplicar atualizações
    context.user_data.update(updates)

def clear_state(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Limpa o estado do usuário.
    
    Args:
        context: Contexto da conversa
    """
    context.user_data.clear()

def is_greeting(text: str, greeting_keywords: List[str]) -> bool:
    """
    Verifica se o texto é uma saudação/mensagem casual e não uma lista de compras.
    
    Args:
        text: Texto da mensagem
        greeting_keywords: Lista de palavras-chave de saudação
        
    Returns:
        True se for uma saudação, False se provavelmente for uma lista
    """
    # Converte para minúsculo para comparação
    text_lower = text.lower().strip()
    
    # Verifica se é uma mensagem curta
    if len(text_lower.split()) <= 5:
        # Verifica se contém palavras-chave de saudação
        for keyword in greeting_keywords:
            if keyword in text_lower:
                return True
        
        # Se for muito curto, provavelmente não é uma lista
        if len(text_lower.split()) <= 2:
            return True
    
    # Verifica características comuns de uma lista de compras
    has_food_items = bool(re.search(r'(arroz|feijão|leite|pão|café|açúcar|sal|óleo|azeite|carne|frango|peixe|legumes|frutas|verduras|macarrão|molho|queijo|manteiga|margarina|ovos|farinha|bolacha|biscoito)', text_lower))
    has_quantity = bool(re.search(r'(kg|g|ml|l|litro|pacote|caixa|lata|unidade|dúzia|un|pote)', text_lower))
    has_comma_separation = ',' in text
    
    # Se tiver características de lista, não é saudação
    if has_food_items or has_quantity or has_comma_separation:
        return False
        
    # Em caso de dúvida, assumimos que é uma saudação
    return True