"""
Módulo responsável pela segurança, criptografia de senhas e geração de tokens JWT.
Utilizando bcrypt de forma nativa e segura, sem dependências obsoletas.
"""
from datetime import datetime, timedelta
import bcrypt
import jwt
from app.core.config import settings
from app.core.logger import setup_logger

from fastapi import WebSocketException, status
from sqlalchemy.orm import Session
from app.models.user_model import User
from app.core.database import SessionLocal

logger = setup_logger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # Token válido por 7 dias

def get_password_hash(password: str) -> str:
    """Gera um hash seguro a partir de uma senha em texto plano usando bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica se a senha em texto plano corresponde ao hash do banco de dados."""
    plain_password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password=plain_password_bytes, hashed_password=hashed_password_bytes)

def create_access_token(data: dict) -> str:
    """Gera um JWT (JSON Web Token) para autenticação do usuário."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    try:
        encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
        return encoded_jwt
    except Exception as e:
        logger.error(f"Erro ao gerar token JWT: {str(e)}")
        raise

def verify_ws_token(token: str) -> User:
    """
    Verifica o token JWT passado via WebSocket (Query Params).
    Retorna o usuário se válido, caso contrário levanta uma exceção de fechamento do WebSocket.
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            logger.warning("Token de WebSocket sem email (sub).")
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
            
        db: Session = SessionLocal()
        user = db.query(User).filter(User.email == email).first()
        db.close()
        
        if user is None:
            logger.warning(f"Usuário não encontrado para o email: {email}")
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
            
        return user
        
    except jwt.ExpiredSignatureError:
        logger.error("Token de WebSocket expirado.")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)
    except jwt.PyJWTError as e:
        logger.error(f"Erro de validação JWT no WebSocket: {str(e)}")
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION)