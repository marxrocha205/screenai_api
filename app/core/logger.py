"""
Módulo de configuração de logs.
Garante que todos os avisos, erros e informações tenham um formato padronizado,
facilitando a depuração local e no console da Railway.
"""
import logging
import sys

def setup_logger(name: str) -> logging.Logger:
    """
    Configura e retorna um logger padronizado.
    
    Args:
        name (str): O nome do módulo que está chamando o logger.
        
    Returns:
        logging.Logger: Instância configurada do logger.
    """
    logger = logging.getLogger(name)
    
    # Evita adicionar múltiplos handlers se o logger já existir
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        
        # O StreamHandler joga os logs para a saída padrão (stdout),
        # que é a melhor prática para aplicações conteinerizadas (Docker/Railway).
        handler = logging.StreamHandler(sys.stdout)

        
        # Formato: Data Hora - Nome do Módulo - Nível (INFO, ERROR) - Mensagem
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
    return logger