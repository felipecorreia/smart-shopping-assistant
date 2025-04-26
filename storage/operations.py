"""
Módulo para operações de alto nível com o BigQuery.
"""

import os
import logging
import csv
from typing import List, Dict, Any, Optional
import pandas as pd

from storage.bigquery_client import BigQueryClient
from data.schema import ProductSchema

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BigQueryOperations:
    """Operações de alto nível com o BigQuery."""
    
    def __init__(
        self,
        project_id: str = None,
        dataset_id: str = None,
        table_id: str = "promotions"
    ):
        """
        Inicializa as operações de BigQuery.
        
        Args:
            project_id: ID do projeto GCP
            dataset_id: ID do dataset BigQuery
            table_id: ID da tabela BigQuery
        """
        self.bq_client = BigQueryClient(project_id, dataset_id, table_id)
        logger.info("Operações de BigQuery inicializadas")
    
    def setup_database(self) -> Dict[str, Any]:
        """
        Configura o banco de dados.
        
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Criar dataset
            dataset_result = self.bq_client.create_dataset_if_not_exists()
            
            if not dataset_result.get("success", False):
                return dataset_result
            
            # Criar tabela
            table_result = self.bq_client.create_table_if_not_exists()
            
            if not table_result.get("success", False):
                return table_result
            
            return {
                "success": True,
                "message": "Banco de dados configurado com sucesso"
            }
        except Exception as e:
            logger.error(f"Erro ao configurar banco de dados: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def validate_product(self, product: Dict[str, Any]) -> Dict[str, Any]:
        """
        Valida um produto usando o esquema.
        
        Args:
            product: Dicionário com dados do produto
            
        Returns:
            Dicionário com resultado da validação
        """
        try:
            # Validar usando Pydantic
            validated_product = ProductSchema(**product)
            
            return {
                "success": True,
                "product": validated_product.dict()
            }
        except Exception as e:
            logger.error(f"Erro ao validar produto: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def import_csv_file(self, file_path: str) -> Dict[str, Any]:
        """
        Importa dados de um arquivo CSV.
        
        Args:
            file_path: Caminho para o arquivo CSV
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            if not os.path.exists(file_path):
                error_message = f"Arquivo não encontrado: {file_path}"
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            # Ler CSV
            df = pd.read_csv(file_path)
            
            # Validar dados
            valid_products = []
            invalid_products = []
            
            for _, row in df.iterrows():
                product = row.to_dict()
                
                # Converter NaN para None
                for key, value in product.items():
                    if pd.isna(value):
                        product[key] = None
                
                validation_result = self.validate_product(product)
                
                if validation_result.get("success", False):
                    valid_products.append(validation_result["product"])
                else:
                    invalid_products.append({
                        "product": product,
                        "error": validation_result.get("error", "Erro desconhecido")
                    })
            
            if not valid_products:
                error_message = "Nenhum produto válido encontrado no arquivo CSV"
                logger.error(error_message)
                return {"success": False, "error": error_message}
            
            # Inserir produtos válidos
            result = self.bq_client.insert_rows(valid_products)
            
            if not result.get("success", False):
                return result
            
            return {
                "success": True,
                "rows_imported": len(valid_products),
                "invalid_rows": len(invalid_products),
                "invalid_details": invalid_products if invalid_products else None
            }
        except Exception as e:
            logger.error(f"Erro ao importar arquivo CSV: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_all_prices_for_product(self, product_name: str) -> List[Dict[str, Any]]:
        """
        Obtém todos os preços para um produto.
        
        Args:
            product_name: Nome do produto
            
        Returns:
            Lista de dicionários com preços
        """
        try:
            return self.bq_client.get_all_prices_for_product(product_name)
        except Exception as e:
            logger.error(f"Erro ao obter preços para o produto '{product_name}': {str(e)}")
            return []
    
    def get_best_price_for_product(self, product_name: str) -> Optional[Dict[str, Any]]:
        """
        Obtém o melhor preço para um produto.
        
        Args:
            product_name: Nome do produto
            
        Returns:
            Dicionário com o melhor preço ou None se não encontrado
        """
        try:
            return self.bq_client.get_best_price_for_product(product_name)
        except Exception as e:
            logger.error(f"Erro ao obter melhor preço para o produto '{product_name}': {str(e)}")
            return None
    
    def get_best_supermarket_for_products(self, product_names: List[str]) -> Dict[str, Any]:
        """
        Obtém o melhor supermercado para uma lista de produtos.
        
        Args:
            product_names: Lista de nomes de produtos
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            return self.bq_client.get_best_supermarket_for_products(product_names)
        except Exception as e:
            logger.error(f"Erro ao obter melhor supermercado: {str(e)}")
            return {"success": False, "error": str(e)}
