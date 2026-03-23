# Usa uma imagem oficial leve do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Impede o Python de gravar arquivos .pyc no disco (otimização)
ENV PYTHONDONTWRITEBYTECODE 1
# Impede o Python de criar buffer de saída (logs aparecem instantaneamente)
ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema necessárias para compilar pacotes como psycopg2
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copia os requisitos e instala as dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código da aplicação
COPY . .

# Comando para rodar a aplicação. Na Railway, a porta é injetada via variável $PORT.
# Usamos um fallback para 8000 caso $PORT não esteja definida.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]