"""
Módulo para integração com o BigQuery.
"""

import os
import logging
from typing import List, Dict, Any, Optional
from google.cloud import bigquery
from google.api_core.exceptions import NotFound

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BigQueryClient:
    """Cliente para interação com o BigQuery."""
    
    def __init__(
        self,
        project_id: str = None,
        dataset_id: str = None,
        table_id: str = "promotions"
    ):
        """
        Inicializa o cliente BigQuery.
        
        Args:
            project_id: ID do projeto GCP
            dataset_id: ID do dataset BigQuery
            table_id: ID da tabela BigQuery
        """
        self.project_id = project_id or os.getenv("BIGQUERY_PROJECT_ID")
        self.dataset_id = dataset_id or os.getenv("BIGQUERY_DATASET_ID", "shopping_assistant")
        self.table_id = table_id
        
        if not self.project_id:
            logger.error("ID do projeto GCP não encontrado. Configure a variável BIGQUERY_PROJECT_ID.")
            raise ValueError("ID do projeto GCP não encontrado")
        
        # Inicializar cliente
        self.client = bigquery.Client(project=self.project_id)
        
        logger.info(f"Cliente BigQuery inicializado para projeto {self.project_id}")
    
    def create_dataset_if_not_exists(self) -> Dict[str, Any]:
        """
        Cria o dataset se não existir.
        
        Returns:
            Dicionário com resultado da operação
        """
        try:
            dataset_ref = self.client.dataset(self.dataset_id)
            
            try:
                self.client.get_dataset(dataset_ref)
                logger.info(f"Dataset {self.dataset_id} já existe")
                return {"success": True, "message": f"Dataset {self.dataset_id} já existe"}
            except NotFound:
                # Dataset não existe, criar
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = "US"
                dataset = self.client.create_dataset(dataset)
                logger.info(f"Dataset {self.dataset_id} criado com sucesso")
                return {"success": True, "message": f"Dataset {self.dataset_id} criado com sucesso"}
        
        except Exception as e:
            logger.error(f"Erro ao criar dataset: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def create_table_if_not_exists(self) -> Dict[str, Any]:
        """
        Cria a tabela se não existir.
        
        Returns:
            Dicionário com resultado da operação
        """
        try:
            table_ref = self.client.dataset(self.dataset_id).table(self.table_id)
            
            try:
                self.client.get_table(table_ref)
                logger.info(f"Tabela {self.table_id} já existe")
                return {"success": True, "message": f"Tabela {self.table_id} já existe"}
            except NotFound:
                # Tabela não existe, criar
                schema = [
                    bigquery.SchemaField("product_id", "INTEGER"),
                    bigquery.SchemaField("product_name", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("price", "FLOAT", mode="REQUIRED"),
                    bigquery.SchemaField("supermarket_name", "STRING", mode="REQUIRED"),
                    bigquery.SchemaField("category", "STRING"),
                    bigquery.SchemaField("unit", "STRING"),
                    bigquery.SchemaField("quantity", "FLOAT"),
                    bigquery.SchemaField("observations", "STRING"),
                    bigquery.SchemaField("folder_link", "STRING"),
                    bigquery.SchemaField("valid_until", "DATE")
                ]
                
                table = bigquery.Table(table_ref, schema=schema)
                table = self.client.create_table(table)
                logger.info(f"Tabela {self.table_id} criada com sucesso")
                return {"success": True, "message": f"Tabela {self.table_id} criada com sucesso"}
        
        except Exception as e:
            logger.error(f"Erro ao criar tabela: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def insert_rows(self, rows: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Insere linhas na tabela.
        
        Args:
            rows: Lista de dicionários com dados a serem inseridos
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            table_ref = self.client.dataset(self.dataset_id).table(self.table_id)
            table = self.client.get_table(table_ref)
            
            errors = self.client.insert_rows_json(table, rows)
            
            if not errors:
                logger.info(f"{len(rows)} linhas inseridas com sucesso")
                return {"success": True, "rows_inserted": len(rows)}
            else:
                logger.error(f"Erros ao inserir linhas: {errors}")
                return {"success": False, "error": str(errors)}
        
        except Exception as e:
            logger.error(f"Erro ao inserir linhas: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def load_data_from_csv(self, file_path: str) -> Dict[str, Any]:
        """
        Carrega dados de um arquivo CSV para a tabela.
        
        Args:
            file_path: Caminho para o arquivo CSV
            
        Returns:
            Dicionário com resultado da operação
        """
        try:
            table_ref = self.client.dataset(self.dataset_id).table(self.table_id)
            
            job_config = bigquery.LoadJobConfig(
                source_format=bigquery.SourceFormat.CSV,
                skip_leading_rows=1,
                autodetect=True
            )
            
            with open(file_path, "rb") as source_file:
                job = self.client.load_table_from_file(
                    source_file, table_ref, job_config=job_config
                )
            
            job.result()  # Aguardar conclusão do job
            
            table = self.client.get_table(table_ref)
            logger.info(f"Carregados {table.num_rows} registros para {self.dataset_id}.{self.table_id}")
            
            return {
                "success": True,
                "rows_loaded": table.num_rows
            }
        
        except Exception as e:
            logger.error(f"Erro ao carregar dados do CSV: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def get_all_prices_for_product(self, product_name: str) -> List[Dict[str, Any]]:
        """
        Busca por produtos usando uma lista de sinônimos normalizados
        """
        try:
            clean_product_name = product_name.strip().lower()
            
            # Mapeamento de termos normalizados
            term_mapping = {
                'açucar': ['açúcar', 'acucar', 'açucar', 'açúcar refinado'],
                'oleo': ['óleo', 'oleo', 'óleo de soja'],
                'sal': ['sal', 'sal refinado']
            }
            
            # Verifica se o termo está no mapeamento
            search_terms = term_mapping.get(clean_product_name, [clean_product_name])
            
            query = f"""
            SELECT
                product_name,
                price,
                supermarket_name,
                category,
                unit,
                quantity,
                observations,
                folder_link,
                CAST(valid_until AS STRING) as valid_until
            FROM
                `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE
                LOWER(product_name) IN UNNEST({search_terms}) OR
                REGEXP_CONTAINS(LOWER(product_name), r'^({"|".join(search_terms)})($| )')
            ORDER BY
                price ASC
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            prices = []
            for row in results:
                prices.append({
                    "product_name": row.product_name,
                    "price": row.price,
                    "supermarket_name": row.supermarket_name,
                    "category": row.category,
                    "unit": row.unit,
                    "quantity": row.quantity,
                    "observations": row.observations,
                    "folder_link": row.folder_link,
                    "valid_until": row.valid_until
                })
            
            logger.info(f"Encontrados {len(prices)} preços para o produto '{clean_product_name}'")
            return prices
        
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
        prices = self.get_all_prices_for_product(product_name)
        
        if prices:
            return prices[0]  # O primeiro é o mais barato devido ao ORDER BY
        
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
            # Construir a condição IN para a consulta
            product_list = ", ".join([f"LOWER('%{name}%')" for name in product_names])
            
            query = f"""
            WITH ProductPrices AS (
                SELECT
                    product_name,
                    price,
                    supermarket_name,
                    category,
                    unit,
                    quantity,
                    observations,
                    folder_link,
                    CAST(valid_until AS STRING) as valid_until
                FROM
                    `{self.project_id}.{self.dataset_id}.{self.table_id}`
                WHERE
                    {" OR ".join([f"LOWER(product_name) LIKE LOWER('%{name}%')" for name in product_names])}
            ),
            SupermarketTotals AS (
                SELECT
                    supermarket_name,
                    SUM(price) as total_price,
                    COUNT(product_name) as product_count
                FROM
                    ProductPrices
                GROUP BY
                    supermarket_name
            )
            SELECT
                supermarket_name,
                total_price,
                product_count
            FROM
                SupermarketTotals
            WHERE
                product_count = {len(product_names)}
            ORDER BY
                total_price ASC
            LIMIT 1
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            rows = list(results)
            
            if not rows:
                logger.info(f"Nenhum supermercado encontrado com todos os produtos")
                return {
                    "success": False,
                    "error": "Nenhum supermercado encontrado com todos os produtos"
                }
            
            best_supermarket = rows[0].supermarket_name
            total_price = rows[0].total_price
            
            # Obter detalhes dos produtos no melhor supermercado
            query = f"""
            SELECT
                product_name,
                price,
                supermarket_name,
                category,
                unit,
                quantity,
                observations,
                folder_link,
                CAST(valid_until AS STRING) as valid_until
            FROM
                `{self.project_id}.{self.dataset_id}.{self.table_id}`
            WHERE
                supermarket_name = '{best_supermarket}'
                AND ({" OR ".join([f"LOWER(product_name) LIKE LOWER('%{name}%')" for name in product_names])})
            """
            
            query_job = self.client.query(query)
            results = query_job.result()
            
            products = []
            for row in results:
                products.append({
                    "product_name": row.product_name,
                    "price": row.price,
                    "supermarket_name": row.supermarket_name,
                    "category": row.category,
                    "unit": row.unit,
                    "quantity": row.quantity,
                    "observations": row.observations,
                    "folder_link": row.folder_link,
                    "valid_until": row.valid_until
                })
            
            logger.info(f"Melhor supermercado: {best_supermarket}, Preço total: {total_price}")
            
            return {
                "success": True,
                "best_supermarket": best_supermarket,
                "total_price": total_price,
                "products": products
            }
        
        except Exception as e:
            logger.error(f"Erro ao obter melhor supermercado: {str(e)}")
            return {"success": False, "error": str(e)}
