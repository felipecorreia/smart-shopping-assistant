"""
Módulo para integração com o WhatsApp via Twilio.
"""

import os
import logging
from typing import Dict, Any, Callable, Optional
from flask import Flask, request
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

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

class WhatsAppBot:
    """Bot do WhatsApp para o assistente de compras inteligente."""
    
    def __init__(
        self, 
        account_sid: str = None, 
        auth_token: str = None, 
        whatsapp_number: str = None
    ):
        """
        Inicializa o bot do WhatsApp.
        
        Args:
            account_sid: SID da conta Twilio
            auth_token: Token de autenticação Twilio
            whatsapp_number: Número do WhatsApp Twilio
        """
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.whatsapp_number = whatsapp_number or os.getenv("TWILIO_WHATSAPP_NUMBER")
        
        if not self.account_sid or not self.auth_token or not self.whatsapp_number:
            logger.error("Credenciais do Twilio não encontradas. Configure as variáveis TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN e TWILIO_WHATSAPP_NUMBER.")
            raise ValueError("Credenciais do Twilio não encontradas")
        
        # Inicializar cliente Twilio
        self.client = Client(self.account_sid, self.auth_token)
        
        # Inicializar aplicação Flask
        self.app = Flask(__name__)
        self.app.route("/webhook", methods=["POST"])(self.webhook)
        
        logger.info("Bot do WhatsApp inicializado")
    
    def send_message(self, to: str, body: str) -> Dict[str, Any]:
        """
        Envia uma mensagem pelo WhatsApp.
        
        Args:
            to: Número de telefone do destinatário
            body: Corpo da mensagem
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Formatar número de telefone
            if not to.startswith("whatsapp:"):
                to = f"whatsapp:{to}"
            
            # Enviar mensagem
            message = self.client.messages.create(
                from_=f"whatsapp:{self.whatsapp_number}",
                body=body,
                to=to
            )
            
            logger.info(f"Mensagem enviada para {to}: {message.sid}")
            return {
                "success": True,
                "message_sid": message.sid
            }
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem para {to}: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def webhook(self):
        """
        Webhook para receber mensagens do WhatsApp.
        
        Returns:
            Resposta TwiML
        """
        try:
            # Obter dados da mensagem
            incoming_msg = request.values.get("Body", "").strip()
            sender = request.values.get("From", "")
            
            logger.info(f"Mensagem recebida de {sender}: {incoming_msg}")
            
            # Criar resposta
            resp = MessagingResponse()
            
            # Verificar se é uma mensagem de ajuda
            if incoming_msg.lower() in ["/start", "/help", "help", "ajuda"]:
                resp.message(
                    "🛒 *Assistente de Compras Inteligente* 🛒\n\n"
                    "Eu posso ajudar você a economizar dinheiro nas suas compras de supermercado!\n\n"
                    "*Como usar:*\n"
                    "Envie sua lista de compras em linguagem natural e eu vou analisar os melhores preços em diferentes supermercados.\n\n"
                    "*Dicas:*\n"
                    "- Seja específico sobre os produtos que deseja\n"
                    "- Você pode incluir quantidades (ex: 2kg de arroz)\n"
                    "- Quanto mais detalhes, melhor será a recomendação"
                )
                return str(resp)
            
            # Enviar mensagem de processamento
            resp.message("🔍 Processando sua lista de compras... Isso pode levar alguns segundos.")
            
            # Iniciar processamento em segundo plano
            # Nota: Em produção, isso deve ser feito de forma assíncrona
            # Para simplificar, estamos processando de forma síncrona aqui
            result = self.process_shopping_list(sender, incoming_msg)
            
            return str(resp)
        
        except Exception as e:
            logger.error(f"Erro no webhook: {str(e)}")
            resp = MessagingResponse()
            resp.message("❌ Ocorreu um erro ao processar sua mensagem. Por favor, tente novamente mais tarde.")
            return str(resp)
    
    def process_shopping_list(self, sender: str, text: str) -> Dict[str, Any]:
        """
        Processa uma lista de compras.
        
        Args:
            sender: Número do remetente
            text: Texto da lista de compras
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Executar pipeline de agentes
            # 1. Agente de compreensão
            understanding_result = run_understanding_agent(text)
            
            if not understanding_result.get("success", False):
                error_message = understanding_result.get("error", "Erro desconhecido ao processar sua lista de compras")
                self.send_message(sender, f"❌ {error_message}")
                return {"success": False, "error": error_message}
            
            shopping_list = ShoppingList(
                items=[
                    item for item in understanding_result.get("shopping_list", {}).get("items", [])
                ]
            )
            
            # 2. Agente de consulta
            query_result = run_query_agent(shopping_list)
            
            if not query_result.get("success", False):
                error_message = query_result.get("error", "Erro desconhecido ao consultar preços")
                self.send_message(sender, f"❌ {error_message}")
                return {"success": False, "error": error_message}
            
            price_options = query_result.get("price_options", {})
            products_not_found = query_result.get("products_not_found", [])
            
            # Verificar se encontrou algum produto
            if not price_options:
                self.send_message(
                    sender, 
                    "❌ Não encontrei nenhum dos produtos da sua lista no nosso banco de dados."
                )
                return {"success": False, "error": "Nenhum produto encontrado"}
            
            # 3. Agente de otimização
            optimization_result = run_optimization_agent(price_options, products_not_found)
            
            if not optimization_result.get("success", False):
                error_message = optimization_result.get("error", "Erro desconhecido ao otimizar compras")
                self.send_message(sender, f"❌ {error_message}")
                return {"success": False, "error": error_message}
            
            recommendation = optimization_result.get("recommendation", {})
            
            # 4. Agente de resposta
            response_result = run_response_agent(recommendation)
            
            if not response_result.get("success", False):
                error_message = response_result.get("error", "Erro desconhecido ao formatar resposta")
                self.send_message(sender, f"❌ {error_message}")
                return {"success": False, "error": error_message}
            
            formatted_response = response_result.get("formatted_response", "")
            
            # Enviar resposta
            self.send_message(sender, formatted_response)
            
            return {"success": True}
            
        except Exception as e:
            logger.error(f"Erro ao processar lista de compras: {str(e)}")
            self.send_message(
                sender,
                f"❌ Ocorreu um erro ao processar sua lista de compras: {str(e)}"
            )
            return {"success": False, "error": str(e)}
    
    def run(self, host: str = "0.0.0.0", port: int = 5000):
        """
        Inicia o servidor Flask.
        
        Args:
            host: Host para o servidor Flask
            port: Porta para o servidor Flask
        """
        logger.info(f"Iniciando servidor Flask em {host}:{port}")
        self.app.run(host=host, port=port)

def main():
    """Função principal para execução direta do módulo."""
    try:
        bot = WhatsAppBot()
        bot.run()
    except Exception as e:
        logger.error(f"Erro ao iniciar bot do WhatsApp: {str(e)}")

if __name__ == "__main__":
    main()
