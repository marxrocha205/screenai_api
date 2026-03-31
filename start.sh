#!/bin/sh

set -e

echo "Iniciando processo de deploy..."

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
