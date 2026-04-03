from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from pydantic import BaseModel

from app.core.database import get_db
from app.core.security import verify_ws_token
from app.core.logger import setup_logger
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.payment_model import PaymentTransaction
from app.models.plan_model import Plan
from app.services.payment_service import payment_service

logger = setup_logger(__name__)
router = APIRouter(prefix="/api/payments", tags=["Pagamentos AlphaPay"])

# No seu painel da AlphaPay, você deve cadastrar seus produtos.
# Substitua as hashes abaixo pelas reais do seu painel!
PLAN_MAPPING = {
    2: {"name": "Plano Pro", "price": 4990, "offer_hash": "hash_oferta_pro", "product_hash": "hash_prod_pro"},
    3: {"name": "Plano Plus", "price": 9990, "offer_hash": "hash_oferta_plus", "product_hash": "hash_prod_plus"}
}

class CheckoutRequest(BaseModel):
    plan_id: int
    full_name: str
    document: str # CPF do cliente
    phone: str

@router.post("/checkout")
async def checkout_pix(request: Request, payload: CheckoutRequest, db: AsyncSession = Depends(get_db)):
    """Rota para o Frontend solicitar o código PIX."""
    auth_header = request.headers.get("Authorization")
    if not auth_header: raise HTTPException(status_code=401)
    
    user_jwt = verify_ws_token(auth_header.split(" ")[1])
    user_id = user_jwt["id"] if isinstance(user_jwt, dict) else user_jwt.id

    if payload.plan_id not in PLAN_MAPPING:
        raise HTTPException(status_code=400, detail="Plano inválido.")

    plan_info = PLAN_MAPPING[payload.plan_id]
    
    # 1. Monta a URL de Webhook dinâmica (para o AlphaPay nos avisar)
    # Substitua pelo seu domínio oficial na nuvem!
    postback_url = ""

    # 2. Chama o Gateway
    user_data = {
        "email": user_jwt.get("email") if isinstance(user_jwt, dict) else user_jwt.email,
        "full_name": payload.full_name,
        "document": payload.document,
        "phone": payload.phone
    }
    
    alpha_res = await payment_service.create_pix_transaction(user_data, plan_info, postback_url)
    
    # Nota: A resposta da AlphaPay geralmente traz o hash e os dados do PIX
    # Exemplo: alpha_res["transaction"]["hash"]
    
    tx_hash = alpha_res.get("hash") or alpha_res.get("transaction_hash", "tx_temp")
    pix_qrcode = alpha_res.get("pix_qrcode", "URL_QRCODE")
    pix_code = alpha_res.get("pix_qrcode_text", "CÓDIGO_COPIA_E_COLA")

    # 3. Salva a transação Pendente no Banco
    nova_tx = PaymentTransaction(
        user_id=user_id,
        plan_id=payload.plan_id,
        gateway_hash=tx_hash,
        amount=plan_info["price"],
        status="pending"
    )
    db.add(nova_tx)
    await db.commit()

    # 4. Devolve para o Frontend mostrar o PIX na tela
    return {
        "status": "success",
        "pix_qrcode_url": pix_qrcode,
        "pix_copy_paste": pix_code,
        "transaction_hash": tx_hash
    }

@router.post("/webhook")
async def alphapay_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """O AlphaPay chama esta rota automaticamente quando o cliente paga."""
    payload = await request.json()
    logger.info(f"Webhook AlphaPay recebido: {payload}")

    tx_hash = payload.get("transaction_hash")
    status_pgto = payload.get("status") # 'paid'

    if not tx_hash or status_pgto != "paid":
        return {"status": "ignored"}

    # 1. Busca a transação
    result = await db.execute(select(PaymentTransaction).where(PaymentTransaction.gateway_hash == tx_hash))
    tx = result.scalars().first()
    if not tx or tx.status == "paid":
        return {"status": "ok"} # Já processado

    # 🛑 PROTEÇÃO CONTRA SPOOFING: Verifica na fonte se é verdade
    is_really_paid = await payment_service.verify_transaction_status(tx_hash)
    if not is_really_paid:
        logger.warning(f"Tentativa de fraude no Webhook interceptada para o hash {tx_hash}")
        raise HTTPException(status_code=400, detail="Transação não consta como paga no Gateway.")
    # 2. Marca transação como Paga
    tx.status = "paid"

    # 3. Atualiza a Assinatura do Usuário!
    result_sub = await db.execute(select(Subscription).where(Subscription.user_id == tx.user_id))
    sub = result_sub.scalars().first()
    
    result_plan = await db.execute(select(Plan).where(Plan.id == tx.plan_id))
    plan = result_plan.scalars().first()

    if sub and plan:
        sub.plan_id = tx.plan_id
        sub.status = "active"
        sub.last_payment_date = datetime.utcnow()
        # Validade de 30 dias
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        # Recarrega os créditos cheios do plano (se aplicável ao Pro/Plus)
        sub.remaining_credits = plan.monthly_credits
        
        await db.commit()
        logger.info(f"Plano {plan.name} ativado com sucesso para o usuário {tx.user_id}!")

    return {"status": "success"}