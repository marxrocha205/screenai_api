from app.core.database import SessionLocal
from sqlalchemy import text

def dar_dinheiro_infinito():
    db = SessionLocal()
    try:
        # SQL Puro: Ignoramos as classes e vamos direto nas tabelas!
        # Nota: assumindo que a sua tabela se chama 'subscriptions' (plural).
        db.execute(text("UPDATE subscriptions SET remaining_credits = 10000, plan_id = 2;"))
        db.commit()
        
        print("✅ Sucesso Absoluto! Foram injetados 10.000 créditos.")
        print("✅ O plano foi atualizado para PRO!")
        
    except Exception as e:
        # Fallback: Se a tabela for no singular ('subscription')
        if "relation \"subscriptions\" does not exist" in str(e):
            db.rollback()
            db.execute(text("UPDATE subscription SET remaining_credits = 10000, plan_id = 2;"))
            db.commit()
            print("✅ Sucesso Absoluto! (Tabela no singular). Créditos injetados.")
        else:
            print(f"❌ Ocorreu um erro SQL: {e}")
            db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    dar_dinheiro_infinito()