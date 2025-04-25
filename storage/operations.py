"""
Módulo para operações de alto nível com o BigQuery.
"""

import os
import logging
import csv
from typing import List, Dict, Any, Optional
import pandas as pd

from storage.bigquery_client import BigQueryClient
from data.schemas import ProductSchema

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
        self.client = BigQueryClient(project_id, dataset_id, table_id)
        logger.info("Operações de BigQuery inicializadas")
    
    def setup_database(self) -> Dict[str, Any]:
        """
        Configura o banco de dados.
        
        Returns:
            Dicionário com resultado da operação
        """
        try:
            # Criar dataset
            dataset_result = self.client.create_dataset_if_not_exists()
            if not dataset_result.get("success", False):
                return dataset_result
            
            # Criar tabela
            table_result = self.client.create_table_if_not_exists()
            if not table_result.get("success", False):
                return table_result
            
            logger.info("Banco de dados configurado com sucesso")
            return {"success": True, "message": "Banco de dados configurado com sucesso"}
        
        except Exception as e:
            logger.error(f"Erro ao configurar banco de dados: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def validate_csv_data(self, file_path: str) -> Dict[str, Any]:
        """
        Valida os dados de um arquivo CSV.
        
        Args:
            file_path: Caminho para o arquivo CSV
            
        Returns:
            Dicionário com resultado da validação
        """
        try:
            # Ler CSV com pandas
            df = pd.read_csv(file_path)
            
            # Verificar colunas obrigatórias
            required_columns = ["product_name", "price", "supermarket_name"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                return {
                    "success": False,
                    "error": f"Colunas obrigatórias ausentes: {', '.join(missing_columns)}"
                }
            
            # Validar cada linha
            valid_rows = []
            invalid_rows = []
            
            for i, row in df.iterrows():
                try:
                    # Converter para dicionário e remover NaN
                    row_dict = row.to_dict()
                    row_dict = {k: v for k, v in row_dict.items() if pd.notna(v)}
                    
                    # Validar com Pydantic
                    product = ProductSchema(**row_dict)
                    valid_rows.append(product.dict(exclude_none=True))
                except Exception as e:
                    invalid_rows.append((i, str(e)))
            
            if invalid_rows:
                logger.warning(f"Encontradas {len(invalid_rows)} linhas inválidas")
                return {
                    "success": False,
                    "error": f"Encontradas {len(invalid_rows)} linhas inválidas",
                    "invalid_rows": invalid_rows,
                    "valid_rows": valid_rows
                }
            
            logger.info(f"CSV validado com sucesso: {len(valid_rows)} linhas válidas")
            return {
                "success": True,
                "valid_rows": valid_rows,
                "rows_count": len(valid_rows)
            }
        
        except Exception as e:
            logger.error(f"Erro ao validar CSV: {str(e)}")
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
            # Validar dados
            validation_result = self.validate_csv_data(file_path)
            
            if not validation_result.get("success", False):
                return validation_result
            
            # Inserir linhas válidas
            valid_rows = validation_result.get("valid_rows", [])
            
            if not valid_rows:
                return {
                    "success": False,
                    "error": "Nenhuma linha válida para importar"
                }
            
            # Usar o método de carregamento de CSV diretamente
            result = self.client.load_data_from_csv(file_path)
            
            if result.get("success", False):
                logger.info(f"CSV importado com sucesso: {result.get('rows_loaded')} linhas")
                return {
                    "success": True,
                    "rows_imported": result.get("rows_loaded")
                }
            else:
                # Fallback: inserir linha por linha
                insert_result = self.client.insert_rows(valid_rows)
                
                if insert_result.get("success", False):
                    logger.info(f"CSV importado com sucesso: {insert_result.get('rows_inserted')} linhas")
                    return {
                        "success": True,
                        "rows_imported": insert_result.get("rows_inserted")
                    }
                else:
                    return insert_result
        
        except Exception as e:
            logger.error(f"Erro ao importar CSV: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def search_products(self, query: str) -> Dict[str, Any]:
        """
        Pesquisa produtos pelo nome.
        
        Args:
            query: Termo de pesquisa
            
        Returns:
            Dicionário com resultado da pesquisa
        """
        try:
            results = self.client.get_all_prices_for_product(query)
            
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
        
        except Exception as e:
            logger.error(f"Erro ao pesquisar produtos: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_prices_for_shopping_list(self, shopping_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Obtém preços para uma lista de compras.
        
        Args:
            shopping_list: Lista de itens de compra
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            price_options = {}
            products_not_found = []
            
            for item in shopping_list:
                product_name = item.get("product_name")
                
                if not product_name:
                    continue
                
                prices = self.client.get_all_prices_for_product(product_name)
                
                if prices:
                    price_options[product_name] = prices
                else:
                    products_not_found.append(product_name)
            
            return {
                "success": True,
                "price_options": price_options,
                "products_not_found": products_not_found
            }
        
        except Exception as e:
            logger.error(f"Erro ao obter preços para lista de compras: {str(e)}")
            return {"success": False, "error": str(e)}
