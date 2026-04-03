import httpx
from fastapi import HTTPException
from app.core.config import settings
from app.core.logger import setup_logger

logger = setup_logger(__name__)

class PaymentService:
    def __init__(self):
        self.base_url = "https://api.alphapaybrasil.com.br/api/public/v1"
        self.token = getattr(settings, "alphapay_api_token", None)

    async def create_pix_transaction(self, user_data: dict, plan_data: dict, postback_url: str):
        """Chama a API da AlphaPay para gerar a transação PIX."""
        if not self.token:
            raise HTTPException(status_code=500, detail="AlphaPay Token não configurado.")

        payload = {
            "amount": plan_data["price"], # Em centavos (Ex: R$49,90 = 4990)
            "offer_hash": plan_data["offer_hash"],
            "payment_method": "pix",
            "customer": {
                "name": user_data["full_name"],
                "email": user_data["email"],
                "phone_number": user_data["phone"],
                "document": user_data["document"] # CPF obrigatório
            },
            "cart": [{
                "product_hash": plan_data["product_hash"],
                "title": plan_data["name"],
                "price": plan_data["price"],
                "quantity": 1,
                "operation_type": 1,
                "tangible": False
            }],
            "expire_in_days": 1,
            "transaction_origin": "api",
            "postback_url": postback_url
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/transactions?api_token={self.token}",
                json=payload,
                headers={"Content-Type": "application/json", "Accept": "application/json"}
            )
            
            if response.status_code != 201:
                logger.error(f"Erro AlphaPay: {response.text}")
                raise HTTPException(status_code=400, detail="Falha ao gerar pagamento no Gateway.")

            return response.json()


    async def verify_transaction_status(self, transaction_hash: str) -> bool:
        """Consulta a AlphaPay para ter certeza absoluta de que foi pago."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/transactions/{transaction_hash}?api_token={self.token}"
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("status") == "paid"
            return False
payment_service = PaymentService()