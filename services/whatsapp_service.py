import json
import logging
from datetime import datetime
import requests
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enviar_mensagem_whatsapp(telefone: str, nome_participante: str, mensagem: str) -> bool:
    """
    Envia uma mensagem de texto para o WhatsApp do participante.
    No modo 'mock' (default), escreve a mensagem estruturada com data e hora no arquivo de log.
    No modo 'production', dispara uma requisição HTTP POST para a API do WhatsApp configurada.
    """
    clean_phone = ''.join(filter(str.isdigit, telefone))
    
    if config.WHATSAPP_API_MODE == "mock":
        try:
            # Garante que a pasta de logs existe
            config.WHATSAPP_LOG_FILE.parent.mkdir(exist_ok=True)
            
            # Formata a linha de log
            log_entry = (
                f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] "
                f"DESTINO: {nome_participante} ({telefone} / Clean: {clean_phone}) | "
                f"MENSAGEM: {mensagem}\n"
                f"{'-'*80}\n"
            )
            
            # Escreve no log local
            with open(config.WHATSAPP_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(log_entry)
                
            logger.info(f"[SIMULAÇÃO WHATSAPP] Notificação gerada para {nome_participante} ({telefone}) no arquivo de log.")
            return True
        except Exception as e:
            logger.error(f"Erro ao salvar log de simulação do WhatsApp: {e}")
            return False
            
    else:
        # Modo Produção - Disparo real via API HTTP
        if not config.WHATSAPP_API_URL:
            logger.error("Modo WhatsApp definido como 'production', mas WHATSAPP_API_URL está ausente!")
            return False
            
        # Payload de exemplo ajustável (comum em Evolution API, Z-API, etc.)
        payload = {
            "number": clean_phone,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "textMessage": {
                "text": mensagem
            }
        }
        
        headers = {
            "Content-Type": "application/json",
            "apikey": config.WHATSAPP_API_TOKEN,
            "Authorization": f"Bearer {config.WHATSAPP_API_TOKEN}" # Suporta ambos os formatos de headers
        }
        
        try:
            response = requests.post(
                config.WHATSAPP_API_URL, 
                data=json.dumps(payload), 
                headers=headers,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                logger.info(f"Mensagem WhatsApp enviada com sucesso para {nome_participante} ({telefone}). Status API: {response.status_code}")
                return True
            else:
                logger.error(f"Erro ao enviar WhatsApp via API: Status {response.status_code} - Resposta: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Falha na requisição HTTP para a API de WhatsApp: {e}")
            return False
