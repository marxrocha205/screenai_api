"""
Controlador de Autenticação.
Gerencia as rotas de registro de usuários e login (geração de token).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from fastapi.security import OAuth2PasswordRequestForm

from app.core.database import get_db
from app.core.logger import setup_logger
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models.user_model import User
from app.schemas.user_schemas import UserCreate, UserResponse, Token

logger = setup_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Autenticação"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Registra um novo usuário no sistema.
    """
    logger.info(f"Tentativa de registro para o email: {user.email}")
    
    # Verifica se o email já existe
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        logger.warning(f"Falha de registro: Email {user.email} já cadastrado.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email já registrado no sistema."
        )
    
    try:
        # Criação do novo usuário
        hashed_pw = get_password_hash(user.password)
        new_user = User(email=user.email, hashed_password=hashed_pw)
        
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        
        logger.info(f"Usuário {user.email} registrado com sucesso. ID: {new_user.id}")
        return new_user
        
    except Exception as e:
        db.rollback()
        logger.error(f"Erro no banco de dados ao registrar usuário: {str(e)}")
        raise HTTPException(status_code=500, detail="Erro interno ao registrar usuário.")

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """
    Autentica o usuário e retorna um token JWT.
    """
    logger.info(f"Tentativa de login para o usuário: {form_data.username}")
    
    # Busca o usuário pelo email (o form_data usa 'username' por padrão no OAuth2)
    user = db.query(User).filter(User.email == form_data.username).first()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        logger.warning(f"Falha de login para {form_data.username}: Credenciais inválidas.")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email ou senha incorretos",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    # Gera o token JWT
    access_token = create_access_token(data={"sub": user.email})
    logger.info(f"Login bem-sucedido para {user.email}")
    
    return {"access_token": access_token, "token_type": "bearer"}