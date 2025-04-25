"""
Módulo para integração com o Telegram.
"""

import os
import logging
from typing import Dict, Any, Callable, Optional
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from agents.understanding.agent import run_understanding_agent
from agents.query.agent import run_query_agent
from agents.optimization.agent import run_optimization_agent
from agents.response.agent import run_response_agent
from data.models import ShoppingList

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Bot do Telegram para o assistente de compras inteligente."""
    
    def __init__(self, token: str = None):
        """
        Inicializa o bot do Telegram.
        
        Args:
            token: Token do bot do Telegram
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not self.token:
            logger.error("Token do bot do Telegram não encontrado. Configure a variável TELEGRAM_BOT_TOKEN.")
            raise ValueError("Token do bot do Telegram não encontrado")
        
        # Inicializar aplicação
        self.application = Application.builder().token(self.token).build()
        
        # Registrar handlers
        self.register_handlers()
        
        logger.info("Bot do Telegram inicializado")
    
    def register_handlers(self):
        """Registra os handlers de comandos e mensagens."""
        # Comandos
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        
        # Mensagens
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Erros
        self.application.add_error_handler(self.error_handler)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Responde ao comando /start.
        
        Args:
            update: Objeto de atualização do Telegram
            context: Contexto do handler
        """
        user = update.effective_user
        await update.message.reply_text(
            f"Olá, {user.first_name}! 👋\n\n"
            "Eu sou o Assistente de Compras Inteligente. Posso ajudar você a economizar dinheiro nas suas compras de supermercado.\n\n"
            "Basta me enviar sua lista de compras e eu vou encontrar os melhores preços para você!\n\n"
            "Por exemplo, você pode enviar:\n"
            "\"Preciso comprar arroz, feijão, 2 litros de leite e café\"\n\n"
            "Use /help para ver mais informações."
        )
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Responde ao comando /help.
        
        Args:
            update: Objeto de atualização do Telegram
            context: Contexto do handler
        """
        await update.message.reply_text(
            "🛒 *Assistente de Compras Inteligente* 🛒\n\n"
            "Eu posso ajudar você a economizar dinheiro nas suas compras de supermercado!\n\n"
            "*Como usar:*\n"
            "1. Envie sua lista de compras em linguagem natural\n"
            "2. Eu vou analisar os melhores preços em diferentes supermercados\n"
            "3. Vou mostrar onde você pode economizar mais\n\n"
            "*Comandos disponíveis:*\n"
            "/start - Inicia a conversa\n"
            "/help - Mostra esta mensagem de ajuda\n\n"
            "*Dicas:*\n"
            "- Seja específico sobre os produtos que deseja\n"
            "- Você pode incluir quantidades (ex: 2kg de arroz)\n"
            "- Quanto mais detalhes, melhor será a recomendação",
            parse_mode="Markdown"
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Processa mensagens de texto.
        
        Args:
            update: Objeto de atualização do Telegram
            context: Contexto do handler
        """
        user_message = update.message.text
        chat_id = update.effective_chat.id
        
        # Enviar mensagem de processamento
        await update.message.reply_text("🔍 Processando sua lista de compras... Isso pode levar alguns segundos.")
        
        # Processar a mensagem de forma assíncrona
        asyncio.create_task(self.process_shopping_list(chat_id, user_message))
    
    async def process_shopping_list(self, chat_id: int, text: str):
        """
        Processa uma lista de compras.
        
        Args:
            chat_id: ID do chat
            text: Texto da lista de compras
        """
        try:
            # Executar pipeline de agentes
            # 1. Agente de compreensão
            understanding_result = run_understanding_agent(text)
            
            if not understanding_result.get("success", False):
                error_message = understanding_result.get("error", "Erro desconhecido ao processar sua lista de compras")
                await self.application.bot.send_message(chat_id=chat_id, text=f"❌ {error_message}")
                return
            
            shopping_list = ShoppingList(
                items=[
                    item for item in understanding_result.get("shopping_list", {}).get("items", [])
                ]
            )
            
            # 2. Agente de consulta
            query_result = run_query_agent(shopping_list)
            
            if not query_result.get("success", False):
                error_message = query_result.get("error", "Erro desconhecido ao consultar preços")
                await self.application.bot.send_message(chat_id=chat_id, text=f"❌ {error_message}")
                return
            
            price_options = query_result.get("price_options", {})
            products_not_found = query_result.get("products_not_found", [])
            
            # Verificar se encontrou algum produto
            if not price_options:
                await self.application.bot.send_message(
                    chat_id=chat_id, 
                    text="❌ Não encontrei nenhum dos produtos da sua lista no nosso banco de dados."
                )
                return
            
            # 3. Agente de otimização
            optimization_result = run_optimization_agent(price_options, products_not_found)
            
            if not optimization_result.get("success", False):
                error_message = optimization_result.get("error", "Erro desconhecido ao otimizar compras")
                await self.application.bot.send_message(chat_id=chat_id, text=f"❌ {error_message}")
                return
            
            recommendation = optimization_result.get("recommendation", {})
            
            # 4. Agente de resposta
            response_result = run_response_agent(recommendation)
            
            if not response_result.get("success", False):
                error_message = response_result.get("error", "Erro desconhecido ao formatar resposta")
                await self.application.bot.send_message(chat_id=chat_id, text=f"❌ {error_message}")
                return
            
            formatted_response = response_result.get("formatted_response", "")
            
            # Enviar resposta
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=formatted_response,
                parse_mode="Markdown"
            )
            
        except Exception as e:
            logger.error(f"Erro ao processar lista de compras: {str(e)}")
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ocorreu um erro ao processar sua lista de compras: {str(e)}"
            )
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Trata erros do bot.
        
        Args:
            update: Objeto de atualização do Telegram
            context: Contexto do handler
        """
        logger.error(f"Erro no bot do Telegram: {context.error}")
        
        if update and update.effective_chat:
            await self.application.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde."
            )
    
    def run(self):
        """Inicia o bot."""
        logger.info("Iniciando bot do Telegram")
        self.application.run_polling()

def main():
    """Função principal para execução direta do módulo."""
    try:
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Erro ao iniciar bot do Telegram: {str(e)}")

if __name__ == "__main__":
    main()
