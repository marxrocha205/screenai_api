"""
Schemas de validação de dados para a API utilizando Pydantic.
Garante que os dados recebidos pelo Controller estejam corretos antes de processá-los.
"""
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    """Schema para validação de criação de usuário."""
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    """Schema para padronizar o retorno dos dados do usuário (omitindo a senha)."""
    id: int
    email: EmailStr
    is_active: bool

    class Config:
        from_attributes = True  # Permite ler dados diretamente do modelo SQLAlchemy

class Token(BaseModel):
    """Schema para retorno do token de autenticação."""
    access_token: str
    token_type: str