#!/bin/sh

# O script irá parar imediatamente se qualquer comando falhar
set -e

echo "Iniciando processo de deploy..."

echo "1. Executando migrações do banco de dados (Alembic)..."
alembic upgrade head

echo "2. Migrações concluídas com sucesso. Iniciando servidor FastAPI..."
# O comando exec substitui o processo atual pelo Uvicorn, o que é melhor para o Docker lidar com sinais de parada (SIGTERM)
# Se a Railway não injetar a porta, usamos a 8000 como fallback
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}