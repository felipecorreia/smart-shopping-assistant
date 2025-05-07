"""
Bot do Telegram para Assistente de Compras Inteligente.
Versão com tratamento robusto de Markdown.
"""

import os
import logging
from typing import Dict, Any, Optional
from functools import partial

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

from agents.understanding.agent import run_understanding_agent
from agents.query.agent import run_query_agent
from agents.optimization.agent import run_optimization_agent
from agents.response.agent import run_response_agent

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Classe principal do Bot com tratamento robusto de Markdown."""

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Token do bot não encontrado")

        self.application = (
            Application.builder()
            .token(self.token)
            .arbitrary_callback_data(True)
            .job_queue(None)
            .build()
        )
        self._register_handlers()
        logger.info("Bot inicializado")

    def _register_handlers(self) -> None:
        """Registra handlers de comandos e mensagens."""
        handlers = [
            CommandHandler("start", self.start_command),
            CommandHandler("help", self.help_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message)
        ]
        for handler in handlers:
            self.application.add_handler(handler)
        self.application.add_error_handler(self.error_handler)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler para /start."""
        user = update.effective_user
        await update.message.reply_text(
            f"Olá {user.first_name}\! 👋\nEu sou seu Assistente de Compras\.\n"
            "Envie sua lista que eu ajudo a economizar\!",
            parse_mode="MarkdownV2"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handler para /help."""
        await update.message.reply_text(
            "✍️ Envie sua lista de compras como texto\.\n"
            "Ex: '2 maçãs, 1kg de arroz, leite'",
            parse_mode="MarkdownV2"
        )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Processa mensagens do usuário."""
        user_message = update.message.text
        chat_id = update.effective_chat.id
        logger.info(f"Mensagem de {chat_id}: {user_message[:50]}...")

        await update.message.reply_text("🔍 Processando sua lista...")
        await self._process_user_request(chat_id, user_message)

    async def _process_user_request(self, chat_id: int, text: str) -> None:
        """Orquestra o processamento da lista de compras."""
        try:
            # Passo 1: Compreensão
            understanding = run_understanding_agent(text)
            if not understanding["success"]:
                return await self._send_error(chat_id, understanding.get("error"))

            # Passo 2: Consulta de preços
            query = run_query_agent(understanding["shopping_list"])
            if not query["success"]:
                return await self._send_error(chat_id, query.get("error"))

            # Passo 3: Otimização
            optimization = run_optimization_agent(
                query["price_options"],
                query.get("products_not_found", [])
            )
            if not optimization["success"]:
                return await self._send_error(chat_id, optimization.get("error"))

            # Passo 4: Resposta
            response = run_response_agent(optimization["recommendation"])
            if not response["success"]:
                return await self._send_error(chat_id, response.get("error"))

            await self._send_response(chat_id, response)

        except Exception as e:
            logger.error(f"Erro no processamento: {e}", exc_info=True)
            await self._send_error(chat_id, f"Erro interno: {str(e)}")

    async def _send_response(self, chat_id: int, response_data: Dict[str, Any]) -> None:
        """Envia a resposta formatada de forma segura."""
        try:
            text = response_data.get("formatted_response", "")
            
            # Primeiro tenta enviar com Markdown (se válido)
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="MarkdownV2",
                    disable_web_page_preview=True
                )
            except Exception as markdown_error:
                logger.warning(f"Erro no Markdown, enviando como texto simples: {markdown_error}")
                # Se falhar, envia como texto simples
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=self._escape_markdown(text),
                    disable_web_page_preview=True
                )
        except Exception as e:
            logger.error(f"Falha ao enviar resposta: {e}")
            await self._send_error(chat_id, "Ocorreu um erro ao formatar a resposta.")

    def _escape_markdown(self, text: str) -> str:
        """Escapa caracteres especiais do Markdown para evitar erros de parsing."""
        escape_chars = '_*[]()~`>#+-=|{}.!'
        return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

    async def _send_error(self, chat_id: int, message: str) -> None:
        """Envia mensagem de erro formatada."""
        try:
            await self.application.bot.send_message(
                chat_id=chat_id,
                text=f"❌ {self._escape_markdown(message)}",
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error(f"Falha ao enviar erro: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Trata erros não capturados."""
        logger.error("Erro no bot:", exc_info=True)
        if update.effective_chat:
            await self._send_error(update.effective_chat.id, "Ocorreu um erro inesperado.")

    def run(self) -> None:
        """Inicia o bot."""
        logger.info("Iniciando bot...")
        self.application.run_polling()

def main():
    """Função principal de inicialização."""
    try:
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logger.error("Falha ao iniciar bot:", exc_info=True)

if __name__ == "__main__":
    main()