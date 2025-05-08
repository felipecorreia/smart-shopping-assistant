"""
Utilitários para formatação de mensagens do Bot do Telegram.
"""

import re
import logging
from typing import Dict, Any, Optional

from telegram import Bot

# Configurar logging
logger = logging.getLogger(__name__)

async def send_text_message(bot: Bot, chat_id: int, text: str, parse_mode: str = "HTML") -> None:
    """
    Envia uma mensagem de texto formatada.
    
    Args:
        bot: Bot do Telegram
        chat_id: ID do chat
        text: Texto da mensagem
        parse_mode: Modo de formatação (HTML ou Markdown)
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem: {e}")
        # Tentar enviar sem formatação
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=strip_formatting(text),
                disable_web_page_preview=True
            )
        except Exception as e2:
            logger.error(f"Erro ao enviar mensagem sem formatação: {e2}")

async def send_error(bot: Bot, chat_id: int, message: str) -> None:
    """
    Envia uma mensagem de erro formatada.
    
    Args:
        bot: Bot do Telegram
        chat_id: ID do chat
        message: Mensagem de erro
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=f"❌ {message}",
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Falha ao enviar erro: {e}")

def convert_markdown_to_html(markdown_text: str) -> str:
    """Converte marcação Markdown para HTML com formatação melhorada."""
    html_text = markdown_text
    
    # Converter títulos com melhor formatação
    html_text = re.sub(r'# (.*?)(?:\n|$)', r'<div style="font-size:20px; font-weight:bold; margin:10px 0;">\1</div>\n', html_text)
    html_text = re.sub(r'## (.*?)(?:\n|$)', r'<div style="font-size:18px; font-weight:bold; margin:8px 0;">\1</div>\n', html_text)
    html_text = re.sub(r'### (.*?)(?:\n|$)', r'<div style="font-size:16px; font-weight:bold; margin:6px 0;">\1</div>\n', html_text)
    
    # Converter negrito
    html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)
    
    # Converter itálico
    html_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html_text)
    
    # Converter listas
    html_text = re.sub(r'- (.*?)(?:\n|$)', r'• \1\n', html_text)
    
    # Limpar caracteres escapados
    html_text = re.sub(r'\\([\\`*_{}[\]()#+\-.!])', r'\1', html_text)
    
    return html_text


def strip_formatting(text: str) -> str:
    """
    Remove completamente a formatação do texto.
    
    Args:
        text: Texto formatado (Markdown ou HTML)
        
    Returns:
        Texto sem formatação
    """
    # Remover formatação HTML
    text = re.sub(r'<[^>]+>', '', text)
    
    # Remover caracteres de escape Markdown
    text = re.sub(r'\\([\\`*_{}[\]()#+\-.!])', r'\1', text)
    
    # Remover formatação de títulos Markdown
    text = re.sub(r'#+\s+(.*?)(?:\n|$)', r'\1\n', text)
    
    # Remover formatação de negrito e itálico Markdown
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    
    return text

def format_recommendation_response(response_data: Dict[str, Any]) -> str:
    """
    Formata a resposta de recomendação para exibição.
    
    Args:
        response_data: Dados da resposta
        
    Returns:
        Texto formatado em HTML
    """
    text = response_data.get("formatted_response", "")
    
    # Converter Markdown para HTML
    html_text = convert_markdown_to_html(text)
    
    return html_text