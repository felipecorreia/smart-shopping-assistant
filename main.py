"""
Módulo principal para o assistente de compras inteligente.
"""

import os
import logging
import argparse
from typing import Dict, Any, List, Optional

from agents.understanding.agent import run_understanding_agent
from agents.refinement.agent import run_refinement_agent
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
    
    def _format_shopping_list_for_display(self, shopping_list: Dict[str, Any]) -> str:
        """
        Formata a lista de compras para exibição ao usuário.
        
        Args:
            shopping_list: Lista de compras
            
        Returns:
            Texto formatado da lista de compras
        """
        items = shopping_list.get("items", [])
        if not items:
            return "Lista vazia"
        
        formatted_items = []
        for i, item in enumerate(items, 1):
            product_name = item.get("product_name", "")
            quantity = item.get("quantity", 1.0)
            unit = item.get("unit", "")
            
            if unit:
                formatted_items.append(f"{i}. {product_name} - {quantity} {unit}")
            else:
                formatted_items.append(f"{i}. {product_name} - {quantity}")
        
        return "\n".join(formatted_items)
    
    def _confirm_shopping_list(self, shopping_list: Dict[str, Any]) -> Dict[str, Any]:
        """
        Solicita confirmação da lista de compras ao usuário.
        
        Args:
            shopping_list: Lista de compras refinada
            
        Returns:
            Lista de compras confirmada ou modificada
        """
        print("\n=== CONFIRME SUA LISTA DE COMPRAS ===")
        print("Por favor, verifique se os itens abaixo estão corretos:")
        print(self._format_shopping_list_for_display(shopping_list))
        print("\nOpções:")
        print("1. Confirmar lista (pressione Enter)")
        print("2. Modificar um item (digite o número do item)")
        print("3. Adicionar um item (digite 'a')")
        print("4. Remover um item (digite 'r' seguido do número do item, ex: r2)")
        print("5. Cancelar (digite 'c')")
        
        response = input("\nSua escolha: ").strip()
        
        if not response:  # Confirmação (Enter)
            return shopping_list
        
        elif response.lower() == 'c':  # Cancelar
            return {"items": []}
        
        elif response.lower() == 'a':  # Adicionar item
            new_item = {}
            new_item["product_name"] = input("Nome do produto: ").strip()
            
            try:
                new_item["quantity"] = float(input("Quantidade (número): ").strip())
            except ValueError:
                new_item["quantity"] = 1.0
                print("Quantidade inválida, usando 1.0 como padrão.")
            
            new_item["unit"] = input("Unidade (kg, l, un, etc. - opcional): ").strip()
            if not new_item["unit"]:
                new_item["unit"] = None
            
            items = shopping_list.get("items", [])
            items.append(new_item)
            
            # Recursivamente pedir confirmação da nova lista
            return self._confirm_shopping_list({"items": items})
        
        elif response.lower().startswith('r'):  # Remover item
            try:
                item_index = int(response[1:]) - 1
                items = shopping_list.get("items", [])
                
                if 0 <= item_index < len(items):
                    removed_item = items.pop(item_index)
                    print(f"Item removido: {removed_item.get('product_name')}")
                else:
                    print("Índice de item inválido.")
                
                # Recursivamente pedir confirmação da nova lista
                return self._confirm_shopping_list({"items": items})
            except (ValueError, IndexError):
                print("Comando inválido para remoção.")
                return self._confirm_shopping_list(shopping_list)
        
        else:  # Modificar item
            try:
                item_index = int(response) - 1
                items = shopping_list.get("items", [])
                
                if 0 <= item_index < len(items):
                    item = items[item_index]
                    print(f"Modificando: {item.get('product_name')}")
                    
                    new_name = input(f"Nome do produto [{item.get('product_name')}]: ").strip()
                    if new_name:
                        item["product_name"] = new_name
                    
                    new_quantity = input(f"Quantidade [{item.get('quantity')}]: ").strip()
                    if new_quantity:
                        try:
                            item["quantity"] = float(new_quantity)
                        except ValueError:
                            print("Quantidade inválida, mantendo o valor anterior.")
                    
                    new_unit = input(f"Unidade [{item.get('unit') or ''}]: ").strip()
                    if new_unit:
                        item["unit"] = new_unit
                    
                    items[item_index] = item
                else:
                    print("Índice de item inválido.")
                
                # Recursivamente pedir confirmação da nova lista
                return self._confirm_shopping_list({"items": items})
            except (ValueError, IndexError):
                print("Comando inválido.")
                return self._confirm_shopping_list(shopping_list)
    
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
            
            # A lista de compras inicial
            initial_list = understanding_result.get("shopping_list", {})
            
            # 2. Agente de refinamento
            refinement_result = run_refinement_agent(initial_list)
            
            if not refinement_result.get("success", False):
                # Se o refinamento falhar, usamos a lista inicial
                logger.warning("Refinamento falhou, usando lista inicial")
                refined_list = initial_list
            else:
                refined_list = refinement_result.get("refined_list", initial_list)
            
            # 3. Confirmação com o usuário
            print("\nLista de compras extraída do seu texto:")
            print(self._format_shopping_list_for_display(initial_list))
            
            if refinement_result.get("success", False) and refined_list != initial_list:
                print("\nLista de compras refinada:")
                print(self._format_shopping_list_for_display(refined_list))
            
            # Solicitar confirmação
            confirmed_list = self._confirm_shopping_list(refined_list)
            
            # Verificar se o usuário cancelou
            if not confirmed_list.get("items", []):
                return {"success": False, "error": "Operação cancelada pelo usuário"}
            
            # 4. Agente de consulta
            # O agente de consulta espera um objeto ShoppingList, mas o código atualizado usa dicionários
            # Vamos converter o dicionário para o objeto ShoppingList para compatibilidade
            shopping_list_obj = ShoppingList(
                items=[
                    ShoppingItem(
                        product_name=item["product_name"],
                        quantity=item.get("quantity", 1.0),
                        unit=item.get("unit")
                    )
                    for item in confirmed_list.get("items", [])
                ]
            )
            query_result = run_query_agent(shopping_list_obj)
            
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
            
            # 5. Agente de otimização
            # Passar o dicionário da lista de compras para o agente de otimização
            optimization_result = run_optimization_agent(price_options, products_not_found, confirmed_list)
            
            if not optimization_result.get("success", False):
                error_message = optimization_result.get("error", "Erro desconhecido ao otimizar compras")
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            recommendation = optimization_result.get("recommendation", {})
            
            # 6. Agente de resposta
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