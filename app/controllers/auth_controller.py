"""
Controlador de Autenticação.
Gerencia as rotas de registro de usuários e login (geração de token).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi.security import OAuth2PasswordRequestForm

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user_model import User
from app.models.plan_model import Plan
from app.models.subscription_model import Subscription
from app.schemas.user_schemas import UserCreate, UserResponse, Token

logger = setup_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registra um novo usuário no sistema.
    """
    logger.info(f"Tentativa de registro para o email: {user.email}")
    
    # Verifica se o email já existe
    result = await db.execute(select(User).filter(User.email == user.email))
    db_user = result.scalars().first()
    if db_user:
        logger.warning(f"Falha de registro: Email {user.email} já cadastrado.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado no sistema."
        )
    
    try:
        # 1. Busca o plano Free no catálogo
        result_plan = await db.execute(select(Plan).filter(Plan.name == "Free"))
        free_plan = result_plan.scalars().first()
        if not free_plan:
            logger.error("Plano 'Free' não encontrado na base de dados. Falha crítica.")
            raise HTTPException(status_code=500, detail="Erro de configuração do sistema.")

        # 2. Cria o novo utilizador
        hashed_pw = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_pw)
        db.add(new_user)
        
        # Dica de Engenharia (flush): 
        # Envia o utilizador para a base de dados para gerar o ID, mas não consolida (commit) ainda.
        # Se a criação da assinatura falhar, o utilizador não será guardado (Transação atómica).
        await db.flush() 
        
        # 3. Cria a Assinatura vinculando o ID do Utilizador ao ID do Plano
        new_subscription = Subscription(
            user_id=new_user.id,
            plan_id=free_plan.id,
            status="active",
            remaining_credits=free_plan.monthly_credits
        )
        db.add(new_subscription)
        
        # 4. Consolida tudo (Utilizador + Assinatura) em segurança
        await db.commit()
        await db.refresh(new_user)
        
        logger.info(f"Utilizador {user.email} registado com plano Free (ID: {new_user.id})")
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erro na base de dados ao registar utilizador: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao registar utilizador.")

@router.post("/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    """
    Autentica o utilizador e gera o token JWT enriquecido com dados de negócio (user_id, plan_id).
    """
    logger.info(f"Tentativa de login para o utilizador: {form_data.username}")
    
    result = await db.execute(select(User).filter(User.email == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Falha de login: Credenciais inválidas para {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Vai buscar os dados da assinatura do utilizador
    result_sub = await db.execute(select(Subscription).filter(Subscription.user_id == user.id))
    subscription = result_sub.scalars().first()
    plan_id = subscription.plan_id if subscription else None
    
    # ENRIQUECIMENTO DO PAYLOAD
    # Em vez de passar apenas o email, passamos um dicionário rico em contexto
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "plan_id": plan_id
            
        }
    )
    
    logger.info(f"Login bem-sucedido para {user.email}. Token gerado.")
    return {"access_token": access_token, "token_type": "bearer"}