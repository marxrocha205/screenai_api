# API Assistente de Acessibilidade

Esta é a API central responsável por gerenciar a comunicação entre o usuário (áudio/texto/imagem) e modelos de Inteligência Artificial.

## Tecnologias Utilizadas
- Python 3.11+
- FastAPI
- SQLAlchemy + PostgreSQL
- Docker

## Como rodar localmente

1. Crie um ambiente virtual: `python -m venv venv` e ative-o.
2. Instale as dependências: `pip install -r requirements.txt`
3. Crie um arquivo `.env` baseado no `.env.example` e configure seu banco de dados local.
4. Inicie o servidor: `uvicorn app.main:app --reload`

## Estrutura
O projeto segue a arquitetura MVC / Clean Architecture, com forte separação de responsabilidades e injeção de dependências.