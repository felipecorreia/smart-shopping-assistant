"""
Processadores de lista de compras para o Bot do Telegram.
"""

import logging
from typing import Dict, Any, List, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from agents.understanding.agent import run_understanding_agent
from agents.refinement.agent import run_refinement_agent
from agents.query.agent import run_query_agent
from agents.optimization.agent import run_optimization_agent
from agents.response.agent import run_response_agent
from data.models import ShoppingList, ShoppingItem

from telegram_states import get_current_state, update_state, clear_state
from telegram_formatters import send_error, send_text_message, format_recommendation_response

# Configurar logging
logger = logging.getLogger(__name__)

async def start_list_processing(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str) -> None:
    """
    Inicia o processamento da lista de compras.
    
    Args:
        update: Objeto de atualização do Telegram
        context: Contexto da conversa
        text: Texto da mensagem com a lista de compras
    """
    chat_id = update.effective_chat.id
    
    try:
        # Passo 1: Compreensão
        
        understanding = run_understanding_agent(text)
        # Verificar número mínimo de itens
        items = understanding["shopping_list"].get("items", [])
        if len(items) < 3:
            await send_text_message(
                context.bot, 
                chat_id,
                f"Identifiquei {len(items)} {'item' if len(items) == 1 else 'itens'} na sua lista: " +
                ", ".join([item.get("product_name", "") for item in items]) + 
                ".\n\nPara uma comparação efetiva de preços, envie pelo menos 3 produtos diferentes. " +
                "Isso permitirá encontrar as melhores ofertas entre diferentes mercados."
            )
            return
        if not understanding["success"]:
            return await send_error(context.bot, chat_id, understanding.get("error"))
            
        # Etapa de Refinamento
        refinement = run_refinement_agent(understanding["shopping_list"])
        if not refinement["success"]:
            logger.warning("Refinamento falhou, usando lista inicial")
            refined_list = understanding["shopping_list"]
            ambiguous_items = {}
        else:
            refined_list = refinement.get("refined_list", understanding["shopping_list"])
            ambiguous_items = refinement.get("ambiguous_items", {})
            
            # Log de informações do refinamento, como correções ortográficas
            corrections = refinement.get("spelling_corrections", {})
            if corrections:
                correction_info = ", ".join([f"{old} → {new['corrected']}" for old, new in corrections.items()])
                logger.info(f"Correções ortográficas: {correction_info}")
        
        # Atualizar o estado com os resultados do refinamento
        # Isso corrige o erro anterior - não atribuímos um novo objeto, 
        # apenas atualizamos o existente
        update_state(context, {
            "refined_list": refined_list,
            "ambiguous_items": ambiguous_items,
            "corrections": refinement.get("spelling_corrections", {})
        })
        
        # Verificar se tem itens ambíguos para mostrar
        if ambiguous_items:
            # Se há ambiguidades, começar a resolvê-las
            update_state(context, {
                "current_ambiguous_items": list(ambiguous_items.keys()),
                "processed_items": {}  # Para armazenar itens já processados
            })
            
            # Mostrar a primeira ambiguidade
            await show_ambiguity_options(update, context)
        else:
            # Se não há ambiguidades, mostrar a lista para confirmação
            await show_list_for_confirmation(update, context)
            
    except Exception as e:
        logger.error(f"Erro no processamento inicial: {e}", exc_info=True)
        await send_error(context.bot, chat_id, f"Erro interno: {str(e)}")

async def show_ambiguity_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Mostra opções para resolver um item ambíguo.
    
    Args:
        update: Objeto de atualização do Telegram
        context: Contexto da conversa
    """
    try:
        # Determinar o chat_id correto
        chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
        
        # Obter o estado atual
        state = get_current_state(context)
        
        # Verificar se ainda há itens ambíguos para processar
        if not state.get("current_ambiguous_items", []):
            # Se não há mais ambiguidades, mostrar a lista para confirmação
            return await show_list_for_confirmation(update, context)
        
        # Obter o próximo item ambíguo
        ambiguous_items = state.get("ambiguous_items", {})
        current_item_name = state.get("current_ambiguous_items", [""])[0]
        variants = ambiguous_items.get(current_item_name, [])
        
        # Criar o teclado com as opções
        keyboard = []
        
        # Adicionar cada variante como um botão
        for i, variant in enumerate(variants):
            variant_name = variant.get("product_name", "")
            callback_data = f"ambig_{i}_{current_item_name}"  # Formato: ambig_índice_nome
            keyboard.append([InlineKeyboardButton(variant_name, callback_data=callback_data)])
        
        # Adicionar opção para manter o original
        keyboard.append([
            InlineKeyboardButton(
                f"Manter \"{current_item_name}\" como está", 
                callback_data=f"ambig_keep_{current_item_name}"
            )
        ])
        
        # Adicionar opção para remover
        keyboard.append([
            InlineKeyboardButton(
                f"Remover este item da lista", 
                callback_data=f"ambig_remove_{current_item_name}"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar mensagem com as opções
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"<b>Encontrei várias opções para \"{current_item_name}\"</b>\n\nPor favor, escolha uma opção:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Erro ao mostrar opções ambíguas: {e}", exc_info=True)
        await send_error(context.bot, chat_id, f"Erro ao mostrar opções: {str(e)}")

async def show_list_for_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Mostra a lista refinada para confirmação pelo usuário.
    
    Args:
        update: Objeto de atualização do Telegram
        context: Contexto da conversa
    """
    try:
        # Determinar o chat_id correto
        chat_id = update.effective_chat.id if update.effective_chat else update.callback_query.message.chat_id
        
        # Obter o estado atual
        state = get_current_state(context)
        refined_list = state.get("refined_list", {"items": []})
        
        # Verificar se há correções ortográficas para mostrar
        corrections = state.get("corrections", {})
        correction_text = ""
        if corrections:
            correction_text = "<b>Correções ortográficas realizadas:</b>\n"
            for old, new in corrections.items():
                correction_text += f"• {old} → {new['corrected']}\n"
            correction_text += "\n"
        
        # Formatar a lista para exibição
        items_text = "<b>Sua lista de compras:</b>\n"
        for i, item in enumerate(refined_list.get("items", []), 1):
            product_name = item.get("product_name", "")
            items_text += f"{i}. {product_name}\n"
        
        # Criar o teclado com as opções de confirmação
        keyboard = [
            [InlineKeyboardButton("✅ Confirmar lista", callback_data="confirm_list")],
            [InlineKeyboardButton("➕ Adicionar item", callback_data="action_add")],
            [InlineKeyboardButton("❌ Cancelar", callback_data="confirm_cancel")]
        ]
        
        # Adicionar botões para modificar/remover se houver itens
        if refined_list.get("items", []):
            keyboard.insert(1, [InlineKeyboardButton("🔄 Modificar um item", callback_data="action_modify")])
            keyboard.insert(2, [InlineKeyboardButton("➖ Remover um item", callback_data="action_remove")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Enviar mensagem para confirmação
        message_text = f"{correction_text}{items_text}\n<b>Confirme sua lista de compras</b>"
        await context.bot.send_message(
            chat_id=chat_id,
            text=message_text,
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
    except Exception as e:
        logger.error(f"Erro ao mostrar lista para confirmação: {e}", exc_info=True)
        await send_error(context.bot, chat_id, f"Erro ao mostrar lista: {str(e)}")

async def process_confirmed_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a lista confirmada pelo usuário.
    
    Args:
        update: Objeto de atualização do Telegram
        context: Contexto da conversa
    """
    try:
        chat_id = update.callback_query.message.chat_id
        
        # Obter o estado atual
        state = get_current_state(context)
        refined_list = state.get("refined_list", {"items": []})
        
        # Converter o dicionário para objeto ShoppingList
        shopping_items = []
        for item in refined_list.get("items", []):
            shopping_item = ShoppingItem(
                product_name=item.get("product_name", ""),
                quantity=item.get("quantity", 1.0),
                unit=item.get("unit")
            )
            shopping_items.append(shopping_item)
        
        shopping_list = ShoppingList(items=shopping_items)
        
        # Obter número total de itens solicitados
        total_requested_items = len(shopping_items)
        
        # Consulta de preços
        query = run_query_agent(shopping_list)
        if not query["success"]:
            return await send_error(context.bot, chat_id, query.get("error"))
        
        # Otimização
        optimization = run_optimization_agent(
            query["price_options"],
            query.get("products_not_found", []),
            total_requested_items
        )
        if not optimization["success"]:
            return await send_error(context.bot, chat_id, optimization.get("error"))
        
        # Resposta
        response = run_response_agent(optimization["recommendation"])
        if not response["success"]:
            return await send_error(context.bot, chat_id, response.get("error"))
        
        # Formatar e enviar resposta
        formatted_html = format_recommendation_response(response)
        await send_text_message(
            context.bot,
            chat_id=chat_id,
            text=formatted_html
        )
        
        # Limpar dados do usuário
        clear_state(context)
        
    except Exception as e:
        logger.error(f"Erro ao processar lista confirmada: {e}", exc_info=True)
        await send_error(context.bot, chat_id, f"Erro interno: {str(e)}")