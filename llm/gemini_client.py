"""
Módulo para integração com o Gemini LLM.
"""

import os
import logging
import json
from typing import List, Dict, Any, Optional
import google.generativeai as genai

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class GeminiClient:
    """Cliente para interação com o Gemini LLM."""
    
    def __init__(self, api_key: str = None):
        """
        Inicializa o cliente Gemini.
        
        Args:
            api_key: Chave de API do Gemini
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            logger.error("Chave de API do Gemini não encontrada. Configure a variável GEMINI_API_KEY.")
            raise ValueError("Chave de API do Gemini não encontrada")
        
        # Configurar Gemini
        genai.configure(api_key=self.api_key)
        
        # Inicializar modelo
        self.model = genai.GenerativeModel('gemini-pro')
        
        logger.info("Cliente Gemini inicializado")
    
    def parse_shopping_list(self, text: str) -> List[Dict[str, Any]]:
        """
        Analisa uma lista de compras em linguagem natural.
        
        Args:
            text: Texto da lista de compras
            
        Returns:
            Lista de itens de compra
        """
        try:
            prompt = f"""
            Analise o texto a seguir e extraia uma lista de compras estruturada.
            
            Texto: "{text}"
            
            Extraia cada item da lista de compras com as seguintes informações:
            - Nome do produto (obrigatório)
            - Quantidade (se especificada, padrão: 1.0)
            - Unidade (se especificada, ex: kg, l, un)
            
            Retorne apenas um array JSON com os itens, sem texto adicional.
            Exemplo de resposta:
            [
                {{"product_name": "arroz", "quantity": 5.0, "unit": "kg"}},
                {{"product_name": "feijão", "quantity": 1.0, "unit": "kg"}},
                {{"product_name": "leite", "quantity": 2.0, "unit": "l"}}
            ]
            """
            
            response = self.model.generate_content(prompt)
            
            # Extrair JSON da resposta
            response_text = response.text
            
            # Limpar a resposta para extrair apenas o JSON
            if "```json" in response_text:
                json_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                json_text = response_text.split("```")[1].strip()
            else:
                json_text = response_text.strip()
            
            # Converter para lista de dicionários
            items = json.loads(json_text)
            
            logger.info(f"Lista de compras analisada com sucesso: {len(items)} itens")
            return items
        
        except Exception as e:
            logger.error(f"Erro ao analisar lista de compras: {str(e)}")
            return []
    
    def format_shopping_recommendation(self, recommendation: Dict[str, Any]) -> str:
        """
        Formata uma recomendação de compras em linguagem natural.
        
        Args:
            recommendation: Recomendação de compras
            
        Returns:
            Texto formatado
        """
        try:
            # Converter recomendação para JSON
            recommendation_json = json.dumps(recommendation, ensure_ascii=False)
            
            prompt = f"""
            Formate a seguinte recomendação de compras em uma mensagem amigável para o usuário.
            
            Recomendação:
            {recommendation_json}
            
            A recomendação contém:
            1. Uma opção de compra em um único supermercado (single_store_option)
            2. Uma opção de compra em múltiplos supermercados (multi_store_option)
            3. A economia potencial (savings) e porcentagem de economia (savings_percentage)
            4. Produtos não encontrados (products_not_found)
            
            Crie uma mensagem que:
            - Seja amigável e útil
            - Explique claramente as opções de compra
            - Destaque a economia potencial
            - Mencione os produtos não encontrados (se houver)
            - Use formatação Markdown para melhorar a legibilidade
            
            Retorne apenas a mensagem formatada, sem texto adicional.
            """
            
            response = self.model.generate_content(prompt)
            
            # Obter texto da resposta
            formatted_text = response.text.strip()
            
            logger.info("Recomendação formatada com sucesso")
            return formatted_text
        
        except Exception as e:
            logger.error(f"Erro ao formatar recomendação: {str(e)}")
            return f"Erro ao formatar recomendação: {str(e)}"
