"""
Módulo principal do Bot do Telegram - Inicialização e configuração
"""

import os
import logging
from typing import Optional

from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters
)

from telegram_handlers import (
    start_command, help_command, handle_message, 
    handle_list_confirmation, handle_ambiguity_selection,
    handle_item_action, handle_modify_item, handle_remove_item,
    handle_back_to_list, error_handler
)

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """Classe principal do Bot do Telegram para o Assistente de Compras Inteligente."""

    def __init__(self, token: Optional[str] = None):
        """
        Inicializa o bot do Telegram.
        
        Args:
            token: Token do bot do Telegram (opcional, pode ser definido via variável de ambiente)
        """
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN")
        if not self.token:
            raise ValueError("Token do bot não encontrado. Configure a variável TELEGRAM_BOT_TOKEN.")

        self.application = (
            Application.builder()
            .token(self.token)
            .arbitrary_callback_data(True)
            .job_queue(None)
            .build()
        )
        self._register_handlers()
        logger.info("Bot do Telegram inicializado")

    def _register_handlers(self) -> None:
        """Registra handlers de comandos e mensagens."""
        handlers = [
            # Comandos básicos
            CommandHandler("start", start_command),
            CommandHandler("help", help_command),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
            
            # Handlers para confirmação de listas
            CallbackQueryHandler(handle_list_confirmation, pattern=r'^confirm_'),
            
            # Handlers para resolução de ambiguidades
            CallbackQueryHandler(handle_ambiguity_selection, pattern=r'^ambig_'),
            
            # Handlers para ações de itens
            CallbackQueryHandler(handle_item_action, pattern=r'^action_'),
            CallbackQueryHandler(handle_modify_item, pattern=r'^modify_'),
            CallbackQueryHandler(handle_remove_item, pattern=r'^remove_'),
            CallbackQueryHandler(handle_back_to_list, pattern=r'^back_to_list$')
        ]
        
        for handler in handlers:
            self.application.add_handler(handler)
        
        # Handler de erros
        self.application.add_error_handler(error_handler)

    def run(self) -> None:
        """Inicia o bot."""
        logger.info("Iniciando bot do Telegram...")
        self.application.run_polling()

def main():
    """Função principal de inicialização."""
    try:
        bot = TelegramBot()
        bot.run()
    except Exception as e:
        logger.error(f"Falha ao iniciar bot do Telegram: {e}", exc_info=True)

if __name__ == "__main__":
    main()