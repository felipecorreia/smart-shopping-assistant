"""
Módulo para importação de dados CSV de exemplo para o BigQuery.
"""

import os
import logging
import argparse
from typing import Dict, Any

from storage.operations import BigQueryOperations

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def import_csv_data(file_path: str) -> Dict[str, Any]:
    """
    Importa dados de um arquivo CSV para o BigQuery.
    
    Args:
        file_path: Caminho para o arquivo CSV
        
    Returns:
        Dicionário com resultado da operação
    """
    try:
        # Verificar se o arquivo existe
        if not os.path.exists(file_path):
            logger.error(f"Arquivo CSV não encontrado: {file_path}")
            return {
                "success": False,
                "error": f"Arquivo CSV não encontrado: {file_path}"
            }
        
        # Inicializar operações de banco de dados
        db_ops = BigQueryOperations()
        
        # Configurar banco de dados (se necessário)
        setup_result = db_ops.setup_database()
        if not setup_result.get("success", False):
            logger.error(f"Erro ao configurar banco de dados: {setup_result.get('error')}")
            return setup_result
        
        # Importar dados do CSV
        import_result = db_ops.import_csv_file(file_path)
        
        return import_result
    
    except Exception as e:
        logger.error(f"Erro ao importar dados CSV: {str(e)}")
        return {
            "success": False,
            "error": f"Erro ao importar dados CSV: {str(e)}"
        }

def main():
    """Função principal para execução direta do módulo."""
    parser = argparse.ArgumentParser(description="Importa dados de um arquivo CSV para o BigQuery")
    parser.add_argument("file_path", help="Caminho para o arquivo CSV")
    args = parser.parse_args()
    
    result = import_csv_data(args.file_path)
    
    if result.get("success", False):
        logger.info("Importação concluída com sucesso!")
        if "rows_imported" in result:
            logger.info(f"Registros importados: {result['rows_imported']}")
    else:
        logger.error(f"Erro na importação: {result.get('error')}")

if __name__ == "__main__":
    main()
