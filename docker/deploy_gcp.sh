#!/bin/bash

# Script para implantar o assistente de compras inteligente no Google Cloud Platform

# Configurações
PROJECT_ID=${BIGQUERY_PROJECT_ID}
REGION="us-central1"
REPOSITORY="smart-shopping-assistant"
IMAGE_NAME="smart-shopping-assistant"
IMAGE_TAG="latest"

# Verificar variáveis de ambiente
if [ -z "$PROJECT_ID" ]; then
  echo "Erro: Variável de ambiente BIGQUERY_PROJECT_ID não definida"
  exit 1
fi

if [ -z "$GEMINI_API_KEY" ]; then
  echo "Erro: Variável de ambiente GEMINI_API_KEY não definida"
  exit 1
fi

# Construir imagens Docker
echo "Construindo imagens Docker..."
docker-compose -f docker/docker-compose.yml build

# Autenticar no Google Cloud
echo "Autenticando no Google Cloud..."
gcloud auth configure-docker

# Criar repositório no Artifact Registry (se não existir)
echo "Configurando repositório no Artifact Registry..."
gcloud artifacts repositories create $REPOSITORY \
  --repository-format=docker \
  --location=$REGION \
  --description="Repositório para o assistente de compras inteligente"

# Marcar imagens para o Artifact Registry
echo "Marcando imagens para o Artifact Registry..."
docker tag smart-shopping-assistant:latest $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
docker tag telegram-bot:latest $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/telegram-bot:$IMAGE_TAG
docker tag whatsapp-bot:latest $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/whatsapp-bot:$IMAGE_TAG

# Enviar imagens para o Artifact Registry
echo "Enviando imagens para o Artifact Registry..."
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:$IMAGE_TAG
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/telegram-bot:$IMAGE_TAG
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/whatsapp-bot:$IMAGE_TAG

# Implantar no Cloud Run
echo "Implantando no Cloud Run..."

# Implantar o aplicativo principal
gcloud run deploy $IMAGE_NAME \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:$IMAGE_TAG \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,BIGQUERY_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET_ID=shopping_assistant"

# Implantar o bot do Telegram
gcloud run deploy telegram-bot \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/telegram-bot:$IMAGE_TAG \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,BIGQUERY_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET_ID=shopping_assistant,TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"

# Implantar o bot do WhatsApp
gcloud run deploy whatsapp-bot \
  --image=$REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/whatsapp-bot:$IMAGE_TAG \
  --platform=managed \
  --region=$REGION \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=$GEMINI_API_KEY,BIGQUERY_PROJECT_ID=$PROJECT_ID,BIGQUERY_DATASET_ID=shopping_assistant,TWILIO_ACCOUNT_SID=$TWILIO_ACCOUNT_SID,TWILIO_AUTH_TOKEN=$TWILIO_AUTH_TOKEN,TWILIO_WHATSAPP_NUMBER=$TWILIO_WHATSAPP_NUMBER"

echo "Implantação concluída com sucesso!"
