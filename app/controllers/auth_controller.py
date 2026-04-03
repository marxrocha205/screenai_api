"""
Controlador de Autenticação.
Gerencia as rotas de registro de usuários e login (geração de token).
Refatorado para operações assíncronas não-bloqueantes (SQLAlchemy 2.0).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os
import secrets
import string
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user_model import User
from app.models.plan_model import Plan
from app.models.subscription_model import Subscription
from app.services.redis_service import redis_service
from app.services.email_service import email_service
from app.schemas.user_schemas import UserCreate, UserResponse, Token,EmailVerificationRequest, GoogleAuthRequest

logger = setup_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/request-code", status_code=status.HTTP_200_OK)
async def request_verification_code(payload: EmailVerificationRequest, db: AsyncSession = Depends(get_db)):
    """
    Passo 1: Gera um código de 6 caracteres, salva no Redis com expiração (15 min) e envia por email.
    """
    email = payload.email.lower()
    
    # 1. Verifica se o email já está registado na base de dados principal
    result_user = await db.execute(select(User).where(User.email == email))
    if result_user.scalars().first():
        # Por segurança, retornamos 200 na mesma para não vazar emails registados para hackers, 
        # mas não enviamos o código de criação de conta.
        logger.warning(f"Tentativa de novo registo com email já existente: {email}")
        return {"message": "Se o email for válido e não estiver registado, receberá um código em instantes."}

    # 2. Gera o código de 6 caracteres (Letras Maiúsculas e Números)
    alfabeto = string.ascii_uppercase + string.digits
    codigo = ''.join(secrets.choice(alfabeto) for _ in range(6))
    
    # 3. Salva no Redis com Time-To-Live (TTL) de 15 minutos (900 segundos)
    redis_key = f"verify_code:{email}"
    await redis_service.redis.setex(redis_key, 900, codigo)
    
    # 4. Envia o email
    await email_service.send_verification_code(to_email=email, code=codigo)
    
    return {"message": "Se o email for válido e não estiver registado, receberá um código em instantes."}



@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user(user: UserCreate, db: AsyncSession = Depends(get_db)):
    """
    Registra um novo usuário no sistema vinculando-o ao plano padrão (Free).
    """
    email = user.email.lower()
    codigo = user.verification_code.upper()
    
    logger.info(f"Tentativa de registro : {email}")
    
    # 1. VALIDAÇÃO NO REDIS
    redis_key = f"verify_code:{email}"
    codigo_guardado = await redis_service.redis.get(redis_key)
    
    if not codigo_guardado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação expirado ou não encontrado. Peça um novo código."
        )
        
    if codigo_guardado != codigo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de verificação incorreto."
        )
    
    # 2. Verifica novamente se o utilizador já existe no PostgreSQL por segurança de concorrência
    result_user = await db.execute(select(User).where(User.email == email))
    if result_user.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email já registado.")
    
    try:
        # 3. Busca o plano Free no catálogo
        result_plan = await db.execute(select(Plan).where(Plan.name == "Free"))
        free_plan = result_plan.scalars().first()
        
        if not free_plan:
            raise HTTPException(status_code=500, detail="Erro de configuração do sistema.")

        # 4. Cria o novo utilizador
        hashed_pw = get_password_hash(user.password)
        new_user = User(email=email, hashed_password=hashed_pw)
        db.add(new_user)
        await db.flush() 
        
        # 5. Cria a Assinatura (Plano Free)
        new_subscription = Subscription(
            user_id=new_user.id,
            plan_id=free_plan.id,
            status="active",
            remaining_credits=free_plan.monthly_credits
        )
        db.add(new_subscription)
        
        # 6. Consolida tudo na base de dados
        await db.commit()
        await db.refresh(new_user)
        
        # 7. SUCESSO! Apaga o código do Redis para evitar reutilização
        await redis_service.redis.delete(redis_key)
        
        logger.info(f"Utilizador {email} registado com sucesso após verificação de email.")
        return new_user
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Erro ao registar utilizador: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao registar utilizador.")


@router.post("/login", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), 
    db: AsyncSession = Depends(get_db)
):
    """
    Autentica o utilizador e gera o token JWT enriquecido com dados de negócio (user_id, plan_id).
    """
    logger.info(f"Tentativa de login para o utilizador: {form_data.username}")
    
    # 1. Busca o utilizador no banco
    result_user = await db.execute(select(User).where(User.email == form_data.username))
    user = result_user.scalars().first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Falha de login: Credenciais inválidas para {form_data.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Busca a assinatura do utilizador para injetar no Token
    result_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result_sub.scalars().first()
    plan_id = subscription.plan_id if subscription else None
    
    # ENRIQUECIMENTO DO PAYLOAD
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "plan_id": plan_id
        }
    )
    
    logger.info(f"Login bem-sucedido para {user.email}. Token gerado.")
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/google", response_model=Token)
async def google_auth(request: GoogleAuthRequest, db: AsyncSession = Depends(get_db)):
    """
    Recebe o ID Token do Google gerado pelo frontend.
    Verifica a autenticidade e realiza login ou registro (Criação de conta Free automática).
    """
    token = request.token
    google_client_id = os.environ.get("GOOGLE_CLIENT_ID")
    
    if not google_client_id:
        logger.error("GOOGLE_CLIENT_ID não configurado no .env.")
        raise HTTPException(status_code=500, detail="Configuração de servidor incompleta para OAuth do Google.")

    try:
        # 1. Autenticar o token recebido no Google
        id_info = id_token.verify_oauth2_token(
            token, google_requests.Request(), google_client_id
        )
        
        # 2. Extrair informações do payload do Google
        email = id_info.get("email")
        name = id_info.get("name")
        
        if not email:
            raise ValueError("O token do Google fornecido não possui o escopo de e-mail.")
            
    except ValueError as e:
        logger.warning(f"Tentativa de login rejeitada pelo Google Auth: {str(e)}")
        raise HTTPException(status_code=400, detail="Verificação do Google falhou: token inválido ou expirado.")

    # 3. Com o Email verificado e garantido pelo Google, validamos a existência local
    result_user = await db.execute(select(User).where(User.email == email))
    user = result_user.scalars().first()
    
    # 4. Se não existe na nossa BD, registramos como um novo User com Plano Free
    if not user:
        logger.info(f"O email Google {email} é novo. Realizando registro automático.")
        try:
            result_plan = await db.execute(select(Plan).where(Plan.name == "Free"))
            free_plan = result_plan.scalars().first()
            
            if not free_plan:
                logger.error("Plano 'Free' em falta durante auto-registro do Google.")
                raise HTTPException(status_code=500, detail="Falha crítica: plano Free ausente.")

            # Para um Login OAuth, a senha perde a utilidade, então geramos uma indecifrável
            alphabet = string.ascii_letters + string.digits + string.punctuation
            rand_pwd = ''.join(secrets.choice(alphabet) for i in range(32))
            
            user = User(email=email, full_name=name, hashed_password=get_password_hash(rand_pwd))
            db.add(user)
            await db.flush()
            
            new_sub = Subscription(
                user_id=user.id,
                plan_id=free_plan.id,
                status="active",
                remaining_credits=free_plan.monthly_credits
            )
            db.add(new_sub)
            await db.commit()
            await db.refresh(user)
            logger.info(f"Novo usuário {email} criado via Google Auth com sucesso.")
            
        except Exception as e:
            await db.rollback()
            logger.error(f"Erro BD no registro via Google: {str(e)}")
            raise HTTPException(status_code=500, detail="Erro interno no registro.")
            
    # 5. GERAR O NOSSO TOKEN (Seja recém-registrado ou login)
    result_sub = await db.execute(select(Subscription).where(Subscription.user_id == user.id))
    subscription = result_sub.scalars().first()
    plan_id = subscription.plan_id if subscription else None
    
    access_token = create_access_token(
        data={
            "sub": user.email,
            "user_id": user.id,
            "plan_id": plan_id
        }
    )
    
    logger.info(f"Autenticação via Google completa para {email}.")
    return {"access_token": access_token, "token_type": "bearer"}