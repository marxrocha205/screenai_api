"""
Controlador de rotas REST para gestão de Perfil de Usuário.
Fornece os dados financeiros e de plano para o frontend.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import jwt

from app.core.database import get_db
from app.core.config import settings
from app.core.logger import setup_logger
from app.models.user_model import User
from app.models.subscription_model import Subscription
from app.models.plan_model import Plan
from app.schemas.user_schemas import UserProfileResponse

logger = setup_logger(__name__)
router = APIRouter(prefix="/users", tags=["Usuários e Perfil"])

# Define onde o Swagger e a aplicação devem procurar o token HTTP
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    """
    Dependência HTTP que valida o JWT e extrai o ID do usuário.
    Diferente da verificação do WebSocket, esta é para rotas REST padrão.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        user_id: int = payload.get("user_id")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token sem identificação de usuário")
        return user_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")


@router.get("/me", response_model=UserProfileResponse)
async def get_user_profile(user_id: int = Depends(get_current_user_id), db: AsyncSession = Depends(get_db)):
    """
    Retorna o perfil completo do usuário autenticado, incluindo os dados
    da assinatura e saldo de créditos atual.
    """
    # 1. Busca o usuário
    result_user = await db.execute(select(User).filter(User.id == user_id))
    user = result_user.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado")
        
    # 2. Busca a assinatura vinculada
    result_sub = await db.execute(select(Subscription).filter(Subscription.user_id == user_id))
    subscription = result_sub.scalars().first()
    
    # 3. Busca o plano para saber o nome e o limite total
    plan = None
    if subscription:
        result_plan = await db.execute(select(Plan).filter(Plan.id == subscription.plan_id))
        plan = result_plan.scalars().first()
    
    # 4. Monta o objeto de resposta mapeando com o Pydantic
    return {
        "id": user.id,
        "email": user.email,
        "plan_name": plan.name if plan else "Sem Plano",
        "subscription_status": subscription.status if subscription else "inactive",
        "remaining_credits": subscription.remaining_credits if subscription else 0,
        "total_monthly_credits": plan.monthly_credits if plan else 0
    }