#!/bin/sh

# O script irá parar imediatamente se qualquer comando falhar
set -e

echo "Iniciando processo de deploy..."

echo "Aguardando o banco de dados estar pronto..."
python -c "
import psycopg2
import sys
import time
import os

db_url = os.environ.get('DATABASE_URL')
if not db_url:
    print('DATABASE_URL não configurada. Pulando check...')
    sys.exit(0)

# Converter postgres:// para postgresql:// se necessário (comum na Railway)
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

while True:
    try:
        conn = psycopg2.connect(db_url)
        conn.close()
        print('Banco de dados pronto!')
        break
    except psycopg2.OperationalError as e:
        print(f'Aguardando banco de dados... {e}')
        time.sleep(2)
"

echo "1. Executando migrações do banco de dados (Alembic)..."
alembic upgrade head

echo "2. Migrações concluídas com sucesso. Iniciando servidor FastAPI..."
# O comando exec substitui o processo atual pelo Uvicorn, o que é melhor para o Docker lidar com sinais de parada (SIGTERM)
# Se a Railway não injetar a porta, usamos a 8000 como fallback
exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}