import os
from pathlib import Path
from dotenv import load_dotenv

# Carrega o arquivo .env
ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)

# Configurações do Banco de Dados Supabase (PostgreSQL)
DATABASE_URL = os.getenv("DATABASE_URL")

# Configurações de Integração com o Backend Go
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

# Configurações de Google APIs
GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "credentials.json")

# Configurações de E-mail SMTP (Envio de links)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_EMAIL = os.getenv("SMTP_EMAIL", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
DEFAULT_DESTINATION_EMAIL = os.getenv("DEFAULT_DESTINATION_EMAIL", "")

# Configurações de Notificação do WhatsApp
WHATSAPP_API_MODE = os.getenv("WHATSAPP_API_MODE", "mock").lower() # 'mock' ou 'production'
WHATSAPP_API_URL = os.getenv("WHATSAPP_API_URL", "")
WHATSAPP_API_TOKEN = os.getenv("WHATSAPP_API_TOKEN", "")

# Caminho para os logs do WhatsApp mock
LOGS_DIR = Path(__file__).parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)
WHATSAPP_LOG_FILE = LOGS_DIR / "whatsapp_envios.log"
