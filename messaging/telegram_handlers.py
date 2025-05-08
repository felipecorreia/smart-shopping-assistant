"""
Handlers para comandos e mensagens do Bot do Telegram.
"""

import logging
from typing import Dict, Any, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from telegram_states import (
    is_greeting, initialize_state,
    get_current_state, update_state
)
from telegram_processors import (
    start_list_processing,
    show_ambiguity_options,
    show_list_for_confirmation,
    process_confirmed_list
)
from telegram_formatters import send_error, send_text_message

# Configurar logging
logger = logging.getLogger(__name__)

# Lista de palavras-chave para saudações comuns
GREETING_KEYWORDS = [
    "oi", "olá", "ola", "bom dia", "boa tarde", "boa noite", 
    "e aí", "eai", "tudo bem", "como vai", "hey", "hi", "hello", "opa", "opah", "salve", "salve salve"
]

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await send_text_message(
        context.bot,
        chat_id=update.effective_chat.id,
        text=f"Olá {user.first_name}! 👋\nEu sou seu Assistente de Compras.\n" +
             "Envie sua lista com pelo menos 3 itens e eu te ajudo a economizar!\n\n"
             "PS: estamos em beta teste rodando para alguns amigos próximos. Podem ocorrer alguns erros. "
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_text_message(
        context.bot,
        chat_id=update.effective_chat.id,
        text="✍️ Envie sua lista de compras com pelo menos 3 itens para uma boa comparação.\n" +
             "Ex: 'Arroz, feijão, açúcar, café, leite'"
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Processa mensagens do usuário."""
    user_message = update.message.text
    chat_id = update.effective_chat.id
    
    # Inicializar o estado do usuário se necessário
    initialize_state(context)
    
    logger.info(f"Mensagem de {chat_id}: {user_message[:50]}...")
    
    # Verificar se estamos no meio de uma operação de adição/modificação
    state = get_current_state(context)
    if state.get("waiting_for_input"):
        action_type = state.get("waiting_for_input")
        
        if action_type == "add_item":
            # Adicionar novo item à lista
            refined_list = state.get("refined_list", {"items": []})
            new_item = {"product_name": user_message.strip(), "quantity": 1.0, "unit": None}
            refined_list["items"].append(new_item)
            
            # Atualizar o estado
            update_state(context, {
                "refined_list": refined_list,
                "waiting_for_input": None
            })
            
            await send_text_message(
                context.bot,
                chat_id=chat_id,
                text=f"✅ Item \"{new_item['product_name']}\" adicionado à lista."
            )
            
            # Mostrar a lista atualizada para confirmação
            await show_list_for_confirmation(update, context)
            return
            
        elif action_type.startswith("modify_item_"):
            # Extrair índice do item a modificar
            index = int(action_type.split("_")[-1])
            
            # Modificar o item
            refined_list = state.get("refined_list", {"items": []})
            if 0 <= index < len(refined_list.get("items", [])):
                old_name = refined_list["items"][index]["product_name"]
                refined_list["items"][index]["product_name"] = user_message.strip()
                
                # Atualizar o estado
                update_state(context, {
                    "refined_list": refined_list,
                    "waiting_for_input": None
                })
                
                await send_text_message(
                    context.bot,
                    chat_id=chat_id,
                    text=f"✅ Item modificado de \"{old_name}\" para \"{user_message.strip()}\"."
                )
            else:
                await send_text_message(
                    context.bot,
                    chat_id=chat_id,
                    text="❌ Erro ao modificar item. Índice inválido."
                )
                
                # Atualizar o estado
                update_state(context, {
                    "waiting_for_input": None
                })
            
            # Mostrar a lista atualizada para confirmação
            await show_list_for_confirmation(update, context)
            return
    
    # Verificar se é uma saudação/mensagem casual
    if is_greeting(user_message, GREETING_KEYWORDS):
        await send_text_message(
            context.bot,
            chat_id=chat_id,
            text="Olá! Estou pronto para te ajudar a pesquisar sua lista de compras e economizar. "
                 "Envie sua pelo menos 3 itens para que eu possa encontrar os melhores preços!"
        )
        return
    # UI de digitação do bot
    

    await send_text_message(context.bot, chat_id, "🔍 Obrigado! Estou entendendo a sua lista...")
    
    # Iniciar processamento da lista
    await start_list_processing(update, context, user_message)

async def handle_list_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a confirmação da lista pelo usuário.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "confirm_list":
            # Lista confirmada, prosseguir com o processamento
            await query.edit_message_text(
                text="✅ Lista confirmada! Agora estou buscando os melhores preços...",
                parse_mode="HTML"
            )
            
            # Continuar com o processamento da lista confirmada
            await process_confirmed_list(update, context)
            
        elif query.data == "confirm_cancel":
            # Usuário cancelou o processamento
            await query.edit_message_text(
                text="❌ Operação cancelada. Envie uma nova lista quando quiser.",
                parse_mode="HTML"
            )
            
            # Limpar dados do usuário
            context.user_data.clear()
            
    except Exception as e:
        logger.error(f"Erro ao processar confirmação: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao processar confirmação: {str(e)}")

async def handle_ambiguity_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a seleção do usuário para um item ambíguo.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        callback_data = query.data  # Formato: ambig_índice_nome ou ambig_keep_nome ou ambig_remove_nome
        state = get_current_state(context)
        refined_list = state.get("refined_list", {"items": []})
        ambiguous_items = state.get("ambiguous_items", {})
        current_ambiguous_items = state.get("current_ambiguous_items", [])
        
        # Verificar o tipo de seleção e item atual
        if callback_data.startswith("ambig_keep_"):
            # Usuário escolheu manter o item original
            item_name = callback_data[len("ambig_keep_"):]
            
            # Não precisa fazer nada, o item já está na lista
            await query.edit_message_text(
                text=f"✅ Item \"{item_name}\" mantido como está.",
                parse_mode="HTML"
            )
            
        elif callback_data.startswith("ambig_remove_"):
            # Usuário escolheu remover o item
            item_name = callback_data[len("ambig_remove_"):]
            
            # Remover o item da lista
            refined_list["items"] = [item for item in refined_list["items"] 
                                     if item.get("product_name") != item_name]
            
            # Atualizar o estado
            update_state(context, {
                "refined_list": refined_list
            })
            
            await query.edit_message_text(
                text=f"❌ Item \"{item_name}\" removido da lista.",
                parse_mode="HTML"
            )
            
        elif callback_data.startswith("ambig_"):
            # Usuário escolheu uma variante específica
            parts = callback_data.split("_", 2)
            index = int(parts[1])
            item_name = parts[2]
            
            # Obter a variante selecionada
            variants = ambiguous_items.get(item_name, [])
            if 0 <= index < len(variants):
                chosen_variant = variants[index]
                variant_name = chosen_variant.get("product_name", "")
                
                # Atualizar o item na lista
                for item in refined_list["items"]:
                    if item.get("product_name") == item_name:
                        item["product_name"] = variant_name
                        break
                
                # Atualizar o estado
                update_state(context, {
                    "refined_list": refined_list
                })
                
                await query.edit_message_text(
                    text=f"✅ Item atualizado para: \"{variant_name}\"",
                    parse_mode="HTML"
                )
        
        # Remover o item atual da lista de ambíguos pendentes
        if current_ambiguous_items:
            current_ambiguous_items.pop(0)
            
            # Atualizar o estado
            update_state(context, {
                "current_ambiguous_items": current_ambiguous_items
            })
        
        # Processar o próximo item ambíguo ou mostrar a lista para confirmação
        if current_ambiguous_items:
            await show_ambiguity_options(update, context)
        else:
            await show_list_for_confirmation(update, context)
        
    except Exception as e:
        logger.error(f"Erro ao processar seleção de ambiguidade: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao processar sua escolha: {str(e)}")

async def handle_item_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa ações de adicionar, modificar ou remover itens.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        action = query.data.split("_")[1]
        state = get_current_state(context)
        
        if action == "add":
            # Entrar no modo de adicionar item
            await query.edit_message_text(
                text="<b>Adicionar item</b>\n\nDigite o nome do produto que deseja adicionar:",
                parse_mode="HTML"
            )
            
            # Atualizar o estado para esperar a entrada do usuário
            update_state(context, {
                "waiting_for_input": "add_item"
            })
            
        elif action == "modify":
            # Mostrar lista de itens para modificar
            refined_list = state.get("refined_list", {"items": []})
            items = refined_list.get("items", [])
            
            if not items:
                await query.edit_message_text(
                    text="Não há itens na lista para modificar.",
                    parse_mode="HTML"
                )
                return
            
            # Criar teclado com itens para modificar
            keyboard = []
            for i, item in enumerate(items):
                product_name = item.get("product_name", "")
                callback_data = f"modify_{i}"
                keyboard.append([InlineKeyboardButton(product_name, callback_data=callback_data)])
            
            # Adicionar botão para cancelar
            keyboard.append([InlineKeyboardButton("↩️ Voltar", callback_data="back_to_list")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="<b>Modificar item</b>\n\nEscolha o item que deseja modificar:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
        elif action == "remove":
            # Mostrar lista de itens para remover
            refined_list = state.get("refined_list", {"items": []})
            items = refined_list.get("items", [])
            
            if not items:
                await query.edit_message_text(
                    text="Não há itens na lista para remover.",
                    parse_mode="HTML"
                )
                return
            
            # Criar teclado com itens para remover
            keyboard = []
            for i, item in enumerate(items):
                product_name = item.get("product_name", "")
                callback_data = f"remove_{i}"
                keyboard.append([InlineKeyboardButton(product_name, callback_data=callback_data)])
            
            # Adicionar botão para cancelar
            keyboard.append([InlineKeyboardButton("↩️ Voltar", callback_data="back_to_list")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                text="<b>Remover item</b>\n\nEscolha o item que deseja remover:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
    except Exception as e:
        logger.error(f"Erro ao processar ação de item: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao processar ação: {str(e)}")

async def handle_modify_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a seleção de um item para modificar.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Extrair o índice do item
        index = int(query.data.split("_")[1])
        state = get_current_state(context)
        refined_list = state.get("refined_list", {"items": []})
        
        if 0 <= index < len(refined_list.get("items", [])):
            item = refined_list["items"][index]
            
            await query.edit_message_text(
                text=f"<b>Modificar item</b>\n\nDigite o novo nome para o item: \"{item.get('product_name', '')}\"",
                parse_mode="HTML"
            )
            
            # Atualizar o estado para esperar a entrada do usuário
            update_state(context, {
                "waiting_for_input": f"modify_item_{index}"
            })
        else:
            await query.edit_message_text(
                text="❌ Erro: item não encontrado.",
                parse_mode="HTML"
            )
            # Voltar para a lista de confirmação
            await show_list_for_confirmation(update, context)
            
    except Exception as e:
        logger.error(f"Erro ao processar modificação de item: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao modificar item: {str(e)}")

async def handle_remove_item(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processa a remoção de um item da lista.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Extrair o índice do item
        index = int(query.data.split("_")[1])
        state = get_current_state(context)
        refined_list = state.get("refined_list", {"items": []})
        
        if 0 <= index < len(refined_list.get("items", [])):
            item = refined_list["items"][index]
            product_name = item.get("product_name", "")
            
            # Remover o item
            refined_list["items"].pop(index)
            
            # Atualizar o estado
            update_state(context, {
                "refined_list": refined_list
            })
            
            await query.edit_message_text(
                text=f"✅ Item \"{product_name}\" removido da lista.",
                parse_mode="HTML"
            )
            
            # Mostrar a lista atualizada
            await show_list_for_confirmation(update, context)
        else:
            await query.edit_message_text(
                text="❌ Erro: item não encontrado.",
                parse_mode="HTML"
            )
            # Voltar para a lista de confirmação
            await show_list_for_confirmation(update, context)
            
    except Exception as e:
        logger.error(f"Erro ao processar remoção de item: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao remover item: {str(e)}")

async def handle_back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Retorna para a tela de confirmação da lista.
    """
    query = update.callback_query
    await query.answer()
    
    try:
        # Voltar para a lista de confirmação
        await show_list_for_confirmation(update, context)
            
    except Exception as e:
        logger.error(f"Erro ao voltar para lista: {e}", exc_info=True)
        await send_error(context.bot, query.message.chat_id, f"Erro ao voltar para lista: {str(e)}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Trata erros não capturados."""
    logger.error("Erro no bot:", exc_info=context.error)
    
    # Tentar enviar mensagem de erro para o usuário
    if update and update.effective_chat:
        await send_error(context.bot, update.effective_chat.id, "Ocorreu um erro inesperado.")