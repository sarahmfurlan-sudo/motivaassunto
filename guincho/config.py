"""Configurações lidas do arquivo .env (copie .env.example para .env)."""
import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def _pasta(nome: str, padrao: str) -> Path:
    p = Path(os.getenv(nome, str(RAIZ / padrao)))
    p.mkdir(parents=True, exist_ok=True)
    return p


# Pastas
PASTA_ENTRADA = _pasta("PASTA_ENTRADA", "entrada")          # onde chegam CSV/XLSX
PASTA_PROCESSADOS = _pasta("PASTA_PROCESSADOS", "processados")
PASTA_ERROS = _pasta("PASTA_ERROS", "erros")
PASTA_SAIDA_EMAILS = _pasta("PASTA_SAIDA_EMAILS", "saida/emails")  # e-mails gerados quando não há SMTP
PASTA_LOGS = _pasta("PASTA_LOGS", "logs")

BANCO = Path(os.getenv("BANCO", str(RAIZ / "dados" / "guincho.db")))
TABELA_RESPONSAVEIS = Path(os.getenv("TABELA_RESPONSAVEIS", str(RAIZ / "dados" / "responsaveis.csv")))

# IA local (Ollama): gratuita, sem cota, roda no próprio computador.
# USAR_IA=nao desliga a IA e usa só o plano B por regras.
USAR_IA = os.getenv("USAR_IA", "sim").strip().lower() in ("sim", "s", "1", "true")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODELO_IA = os.getenv("MODELO_IA", "qwen2.5:3b")
IA_MAX_TOKENS = int(os.getenv("IA_MAX_TOKENS", "600"))   # tamanho máximo da resposta da IA
IA_TIMEOUT = int(os.getenv("IA_TIMEOUT", "120"))         # segundos de espera pela IA
# Abaixo desta confiança, o pedido vai para a triagem humana do CCO em vez de ir direto à base.
CONFIANCA_MINIMA = float(os.getenv("CONFIANCA_MINIMA", "0.6"))

# Caixa que recebe os pedidos (IMAP)
IMAP_HOST = os.getenv("IMAP_HOST", "")
IMAP_USUARIO = os.getenv("IMAP_USUARIO", "")
IMAP_SENHA = os.getenv("IMAP_SENHA", "")
IMAP_PASTA = os.getenv("IMAP_PASTA", "INBOX")

# Envio do encaminhamento (SMTP). Sem SMTP_HOST, o e-mail é salvo como .eml em saida/emails.
SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORTA = int(os.getenv("SMTP_PORTA", "587"))
SMTP_USUARIO = os.getenv("SMTP_USUARIO", "")
SMTP_SENHA = os.getenv("SMTP_SENHA", "")
EMAIL_REMETENTE = os.getenv("EMAIL_REMETENTE", SMTP_USUARIO or "automacao@exemplo.com.br")
# Modo demonstração: todos os encaminhamentos vão para este endereço (os responsáveis são fictícios).
EMAIL_DEMO_PARA = os.getenv("EMAIL_DEMO_PARA", "")

INTERVALO_SEGUNDOS = int(os.getenv("INTERVALO_SEGUNDOS", "30"))
