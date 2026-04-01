"""
Schemas de validação de dados para a API utilizando Pydantic.
Garante que os dados recebidos pelo Controller estejam corretos antes de processá-los.
"""
from pydantic import BaseModel, EmailStr, Field

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

class UserProfileResponse(BaseModel):
    """
    Schema para retornar o perfil completo do painel do cliente, 
    incluindo os dados financeiros da assinatura e saldo atual.
    """
    id: int
    email: EmailStr
    plan_name: str
    subscription_status: str
    remaining_credits: int
    total_monthly_credits: int

    class Config:
        from_attributes = True  # Permite ler dados diretamente do modelo SQLAlchemy

# ==========================================
# NOVOS SCHEMAS (ÁREA ADMINISTRATIVA)
# ==========================================

class UserStatusUpdate(BaseModel):
    """
    Schema de validação para a atualização do estado do utilizador (Admin).
    Isola a mutação garantindo que apenas o campo 'is_active' possa ser alterado,
    protegendo contra injeção de outros dados (ex: is_admin).
    """
    is_active: bool = Field(
        ..., 
        description="O novo estado de ativação do utilizador (True para ativo, False para suspenso)."
    )
    
class AdminCreditUpdate(BaseModel):
    """
    Schema de validação para a injeção ou remoção manual de créditos.
    """
    amount: int = Field(
        ..., 
        description="Quantidade de créditos a adicionar (positivo) ou remover (negativo)."
    )
    reason: str = Field(
        ..., 
        min_length=5,
        description="Justificação obrigatória para a auditoria (ex: 'Reembolso por falha na API')."
    )

class GoogleAuthRequest(BaseModel):
    """Schema para validação do token do Google recebido do frontend."""
    token: str = Field(..., description="O JWT token retornado pelo Google Identity Services.")