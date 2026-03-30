# Lógica de Negócio - ScreenAI API

Este documento descreve a lógica de negócio principal da API ScreenAI, detalhando o funcionamento dos Planos, Assinaturas, Sistema de Créditos (Pedágio) e como seria a integração com um Gateway de Pagamentos.

---

## 1. Planos (Tiers) e Arbitragem de IA

O sistema possui um catálogo de planos predefinidos (Seed) na base de dados, cada um oferecendo um nível diferente de benefícios, cota de créditos mensais e acesso a modelos de inteligência artificial de diferentes capacidades.

| ID | Plano | Preço (R$) | Créditos Mensais | Modelo de IA Roteado | Voz Premium |
|---|---|---|---|---|---|
| 1 | **Free** | 0,00 | 100 | `gemini-2.5-flash-lite` | Não (Usa TTS Nativo do Navegador) |
| 2 | **Pro** | 44,90 | 1500 | `gemini-2.5-flash` | Sim (OpenAI TTS) |
| 3 | **Plus** | 89,90 | 4000 | `gemini-2.5-pro` | Sim (OpenAI TTS) |

A **Arbitragem de IA** ocorre no `GeminiService`: dependendo do `plan_id` atrelado ao usuário, o sistema direciona a requisição para um modelo mais barato e rápido (Flash Lite) ou mais caro e inteligente (Pro).

---

## 2. Sistema de Cobrança e Consumo (O Pedágio)

Toda interação via WebSocket custa "energia" (créditos). O `BillingService` é consultado antes de cada geração de resposta da IA para garantir que o usuário tenha saldo suficiente (`remaining_credits` na tabela de Assinaturas).

**Tabela de Custos por Interação:**
- **Texto / Base:** 1 crédito
- **Análise de Imagem (Screen / Câmera):** + 5 créditos
- **Voz Premium (OpenAI TTS):** + 50 créditos (Apenas cobrado e utilizado nos planos Pro e Plus)

*Exemplo:* Uma mensagem de áudio (transcrita), com uma imagem anexada, enviada por um usuário Pro custará: `1 (Base) + 5 (Imagem) + 50 (Voz Premium) = 56 créditos`.

Se o usuário não tiver saldo, o WebSocket retorna uma mensagem de erro orientando a fazer um upgrade.

---

## 3. Gestão de Assinaturas (Subscriptions)

O modelo `Subscription` é a ponte entre o `User` (Usuário) e o `Plan` (Plano). Ele controla:
*   `plan_id`: Qual plano o usuário possui no momento.
*   `remaining_credits`: O saldo atual de créditos do usuário.
*   `status`: O estado financeiro (`active`, `past_due`, `canceled`).
*   `current_period_end`: A data em que o ciclo mensal vira.

Quando um usuário se cadastra, ele é automaticamente atribuído ao **Plano Free (ID 1)** e sua assinatura é criada com 100 créditos (`active`).

---

## 4. Integração com Gateway de Pagamentos (Ex: Stripe, Pagar.me, Mercado Pago)

Para monetizar este sistema, você não processa cartões diretamente, mas delega isso a um Gateway. A arquitetura sugerida para essa implementação é:

### Fluxo de Assinatura (Checkout)
1. **Frontend:** O usuário clica em "Assinar Pro".
2. **Backend:** Um novo endpoint (`POST /api/billing/checkout`) chama a API do Gateway (ex: Stripe) criando uma "Sessão de Checkout".
3. **Redirecionamento:** O backend devolve a URL segura do Stripe. O usuário é redirecionado, insere o cartão lá e paga.
4. **Retorno:** O usuário é mandado de volta para o seu site (URL de sucesso).

### O Papel Essencial dos Webhooks
O backend não sabe imediatamente se o cartão passou. Para isso, precisamos criar um endpoint de escuta (`POST /api/webhooks/gateway`).

Quando o pagamento é aprovado, o Gateway dispara um evento (ex: `invoice.paid` no Stripe) para o seu Webhook. A lógica do Webhook seria:

```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    # 1. Validar a assinatura de segurança do payload
    event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    
    # 2. Processar o pagamento aprovado
    if event['type'] == 'invoice.paid':
        customer_email = event['data']['object']['customer_email']
        # Buscar usuário no DB
        user = db.query(User).filter(User.email == customer_email).first()
        
        # 3. Atualizar a Assinatura (Subscription)
        subscription = db.query(Subscription).filter(Subscription.user_id == user.id).first()
        subscription.plan_id = 2 # Ex: Mudou para o Pro
        subscription.status = "active"
        subscription.remaining_credits += 1500 # Adiciona os créditos mensais
        # Define a próxima cobrança para daqui a 30 dias
        subscription.current_period_end = datetime.now() + timedelta(days=30) 
        db.commit()
        
    return {"status": "success"}
```

### O Ciclo Mensal (Renovação Automática)
Todo mês, o Gateway vai tentar cobrar o cartão do cliente automaticamente.
*   Se passar: Dispara outro `invoice.paid`. Seu Webhook recebe e adiciona mais 1500 créditos (ou zera e coloca 1500, dependendo da sua regra de acúmulo).
*   Se o cartão recusar: O Gateway dispara um evento `invoice.payment_failed`. Seu Webhook recebe isso e muda o `status` da assinatura do usuário para `past_due`. O próximo acesso dele ao WebSocket será negado.
