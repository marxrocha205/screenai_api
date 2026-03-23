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

## Testes Locais com Banco de Dados

Para rodar o banco de dados localmente sem poluir sua máquina, utilize o Docker Compose:
`docker-compose up -d`

A API criará as tabelas automaticamente na primeira execução graças ao `Base.metadata.create_all(bind=engine)`.

## Testando o WebSocket Localmente

1. Suba a aplicação (`uvicorn app.main:app --reload`).
2. Acesse `http://127.0.0.1:8000/docs`, crie um usuário em `/auth/register` e faça login em `/auth/login` para obter o `access_token`.
3. Abra o arquivo `teste_ws.html` no seu navegador.
4. Cole o token no campo indicado, clique em "Conectar" e depois em "Enviar Teste". Você verá o eco do servidor em tempo real.

## Registro e Commit

O código agora possui memória. A "Linha de Raciocínio do Cliente", regra fundamental do seu prompt, agora é tecnicamente possível, pois o Gemini sabe exatamente em qual etapa do "passo a passo" o usuário está.

## Arquitetura de Comunicação (Rotas)

O sistema possui duas vias de comunicação com a Inteligência Artificial, projetadas para escalabilidade:

### 1. Comunicação Tempo Real (WebSocket)
- **Rota:** `ws://host/ws/assistente?token=...`
- **Uso:** Ideal para o núcleo do ScreenAI. O usuário transmite voz/texto e prints de tela compactados continuamente. O servidor responde instantaneamente mantendo o canal aberto.

### 2. Comunicação Tradicional / Uploads Pesados (REST)
- **Rota:** `POST /api/chat/message?token=...`
- **Uso:** Rota HTTP padrão (Multipart/Form-Data). Ideal para quando o usuário precisa enviar um áudio longo gravado, um documento PDF de várias páginas ou imagens em alta resolução. A API gerencia o upload para a nuvem do Google e acopla a análise ao histórico do usuário.
- **Parâmetros:** Aceita os campos `text` (String) e `file` (Arquivo).