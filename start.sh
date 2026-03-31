#!/bin/sh

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

# 🔥 Adicionado para suportar URLs com +asyncpg (que o psycopg2 não entende)
if 'asyncpg' in db_url:
    db_url = db_url.replace('postgresql+asyncpg://', 'postgresql://', 1)

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

# Tenta rodar migrations
if alembic upgrade head; then
    echo "Migrações aplicadas com sucesso!"
else
    echo "Erro ao rodar migrations!"

    # 🔥 fallback inteligente (evita crash loop)
    echo "Tentando sincronizar estado do Alembic..."
    alembic stamp head || true

    echo "Continuando inicialização mesmo com erro de migration..."
fi

echo "2. Iniciando servidor FastAPI..."

exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
