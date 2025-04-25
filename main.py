"""
Módulo principal para o assistente de compras inteligente.
"""

import os
import logging
import argparse
from typing import Dict, Any, List, Optional

from agents.understanding.agent import run_understanding_agent
from agents.query.agent import run_query_agent
from agents.optimization.agent import run_optimization_agent
from agents.response.agent import run_response_agent
from storage.operations import BigQueryOperations
from data.models import ShoppingList, ShoppingItem

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ShoppingAssistant:
    """Assistente de compras inteligente."""
    
    def __init__(self):
        """Inicializa o assistente de compras."""
        self.db_ops = BigQueryOperations()
        logger.info("Assistente de compras inicializado")
    
    def setup(self) -> Dict[str, Any]:
        """
        Configura o banco de dados.
        
        Returns:
            Dicionário com resultado da operação
        """
        return self.db_ops.setup_database()
    
    def import_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Importa dados de um arquivo CSV.
        
        Args:
            file_path: Caminho para o arquivo CSV
            
        Returns:
            Dicionário com resultado da operação
        """
        return self.db_ops.import_csv_file(file_path)
    
    def process_shopping_list(self, text: str) -> Dict[str, Any]:
        """
        Processa uma lista de compras em linguagem natural.
        
        Args:
            text: Texto da lista de compras
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # 1. Agente de compreensão
            understanding_result = run_understanding_agent(text)
            
            if not understanding_result.get("success", False):
                error_message = understanding_result.get("error", "Erro desconhecido ao processar sua lista de compras")
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            shopping_list = ShoppingList(
                items=[
                    ShoppingItem(
                        product_name=item["product_name"],
                        quantity=item.get("quantity", 1.0),
                        unit=item.get("unit")
                    )
                    for item in understanding_result.get("shopping_list", {}).get("items", [])
                ]
            )
            
            # 2. Agente de consulta
            query_result = run_query_agent(shopping_list)
            
            if not query_result.get("success", False):
                error_message = query_result.get("error", "Erro desconhecido ao consultar preços")
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            price_options = query_result.get("price_options", {})
            products_not_found = query_result.get("products_not_found", [])
            
            # Verificar se encontrou algum produto
            if not price_options:
                error_message = "Não encontrei nenhum dos produtos da sua lista no nosso banco de dados."
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            # 3. Agente de otimização
            optimization_result = run_optimization_agent(price_options, products_not_found)
            
            if not optimization_result.get("success", False):
                error_message = optimization_result.get("error", "Erro desconhecido ao otimizar compras")
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            recommendation = optimization_result.get("recommendation", {})
            
            # 4. Agente de resposta
            response_result = run_response_agent(recommendation)
            
            if not response_result.get("success", False):
                error_message = response_result.get("error", "Erro desconhecido ao formatar resposta")
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            formatted_response = response_result.get("formatted_response", "")
            
            logger.info("Lista de compras processada com sucesso")
            return {
                "success": True,
                "recommendation": recommendation,
                "formatted_response": formatted_response
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar lista de compras: {str(e)}")
            return {"success": False, "error": str(e)}

def main():
    """Função principal para execução direta do módulo."""
    parser = argparse.ArgumentParser(description="Assistente de compras inteligente")
    subparsers = parser.add_subparsers(dest="command", help="Comando a ser executado")
    
    # Comando setup
    setup_parser = subparsers.add_parser("setup", help="Configura o banco de dados")
    
    # Comando import
    import_parser = subparsers.add_parser("import", help="Importa dados de um arquivo CSV")
    import_parser.add_argument("file_path", help="Caminho para o arquivo CSV")
    
    # Comando process
    process_parser = subparsers.add_parser("process", help="Processa uma lista de compras")
    process_parser.add_argument("text", help="Texto da lista de compras")
    
    args = parser.parse_args()
    
    assistant = ShoppingAssistant()
    
    if args.command == "setup":
        result = assistant.setup()
        if result.get("success", False):
            logger.info("Banco de dados configurado com sucesso")
        else:
            logger.error(f"Erro ao configurar banco de dados: {result.get('error')}")
    
    elif args.command == "import":
        result = assistant.import_csv(args.file_path)
        if result.get("success", False):
            logger.info(f"Dados importados com sucesso: {result.get('rows_imported', 0)} registros")
        else:
            logger.error(f"Erro ao importar dados: {result.get('error')}")
    
    elif args.command == "process":
        result = assistant.process_shopping_list(args.text)
        if result.get("success", False):
            print("\n" + result.get("formatted_response", ""))
        else:
            logger.error(f"Erro ao processar lista de compras: {result.get('error')}")
    
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
