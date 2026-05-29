import base64
import logging
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from google.auth.transport.requests import Request as GoogleRequest
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials as OAuth2Credentials
from googleapiclient.discovery import build

from database import db_cursor
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _obter_credenciais_usuario(user_id: str, scopes: list[str]):
    if not user_id:
        return None

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        logger.warning("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET ausentes; nao foi possivel usar Gmail API do usuario.")
        return None

    try:
        with db_cursor() as cursor:
            cursor.execute(
                "SELECT access_token, refresh_token, token_type, expires_at FROM google_oauth_tokens WHERE user_id = %s LIMIT 1;",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None

            access_token, refresh_token, token_type, expires_at = row
            creds = OAuth2Credentials(
                token=access_token,
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=client_id,
                client_secret=client_secret,
                scopes=scopes,
            )

            if creds.expired and creds.refresh_token:
                logger.info("Atualizando credencial do usuario para envio de e-mail via Gmail API...")
                creds.refresh(GoogleRequest())
                with db_cursor() as update_cursor:
                    update_cursor.execute(
                        "UPDATE google_oauth_tokens SET access_token = %s, expires_at = %s, token_type = %s WHERE user_id = %s;",
                        (creds.token, creds.expiry, creds.token_type or token_type, user_id)
                    )

            return creds
    except Exception as err:
        logger.warning(f"Nao foi possivel carregar credenciais do usuario para Gmail API: {err}")
        return None


def _enviar_via_gmail_api(creds, destinatario: str, assunto: str, html_content: str) -> bool:
    gmail_service = build("gmail", "v1", credentials=creds)

    logger.info(f"Enviando e-mail via Gmail API para {destinatario}")

    message = MIMEMultipart("alternative")
    message["To"] = destinatario
    message["Subject"] = assunto
    message.attach(MIMEText(html_content, "html"))

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    gmail_service.users().messages().send(
        userId="me",
        body={"raw": raw_message},
    ).execute()
    return True

def enviar_email_formulario(
    tema_treinamento: str,
    link_formulario: str,
    email_destinatario: str = None,
    user_id: str = None,
) -> bool:
    """
    Dispara um e-mail HTML moderno contendo o link de inscrição para o treinamento.
    Prioriza Gmail API usando as credenciais do usuario conectado.
    """
    destinatario = email_destinatario or config.DEFAULT_DESTINATION_EMAIL
    
    if not destinatario:
        logger.warning("Nenhum e-mail de destino configurado ou fornecido. O e-mail não será enviado.")
        return False

    # Assunto do e-mail
    assunto = f"Inscrições Abertas: Treinamento - {tema_treinamento}"

    # Corpo do e-mail com layout premium
    html_content = f"""
    <!DOCTYPE html>
    <html lang="pt-BR">
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Outfit', 'Inter', 'Helvetica Neue', Arial, sans-serif;
                background-color: #F7F4EF;
                margin: 0;
                padding: 0;
                color: #1F2937;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.05), 0 8px 10px -6px rgba(0, 0, 0, 0.05);
                border: 1px solid #E5E7EB;
            }}
            .header {{
                background: linear-gradient(135deg, #8B1A1A 0%, #D93030 100%);
                padding: 40px 20px;
                text-align: center;
                color: #ffffff;
            }}
            .header h1 {{
                margin: 0;
                font-size: 26px;
                font-weight: 700;
                letter-spacing: -0.5px;
            }}
            .content {{
                padding: 40px 30px;
                line-height: 1.6;
            }}
            .content p {{
                margin-top: 0;
                margin-bottom: 20px;
                font-size: 16px;
            }}
            .highlight-box {{
                background-color: #FFF5F5;
                border-left: 4px solid #D93030;
                padding: 15px;
                margin: 25px 0;
                border-radius: 0 8px 8px 0;
            }}
            .highlight-box strong {{
                color: #8B1A1A;
            }}
            .button-wrapper {{
                text-align: center;
                margin: 35px 0 15px 0;
            }}
            .btn {{
                background: linear-gradient(135deg, #D93030 0%, #8B1A1A 100%);
                color: #ffffff !important;
                text-decoration: none;
                padding: 14px 30px;
                font-size: 16px;
                font-weight: 600;
                border-radius: 30px;
                display: inline-block;
                box-shadow: 0 4px 6px -1px rgba(217, 48, 48, 0.2);
                transition: transform 0.2s ease, box-shadow 0.2s ease;
            }}
            .footer {{
                background-color: #f9fafb;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #6b7280;
                border-top: 1px solid #e5e7eb;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Treinamento Flamboyant</h1>
            </div>
            <div class="content">
                <p>Olá,</p>
                <p>Temos a satisfação de anunciar um novo treinamento voltado para o desenvolvimento e integração de nossa equipe de lojistas no Shopping Flamboyant.</p>
                
                <div class="highlight-box">
                    <strong>Tópico do Evento:</strong> {tema_treinamento}<br>
                    <strong>Objetivo:</strong> Capacitação comercial e operacional das lojas.
                </div>
                
                <p>As inscrições já estão abertas e podem ser realizadas online através do formulário exclusivo do Google Forms que geramos para este evento. Por favor, preencha as informações do representante que irá comparecer.</p>
                
                <div class="button-wrapper">
                    <a href="{link_formulario}" class="btn" target="_blank">Acessar Formulário de Inscrição</a>
                </div>
            </div>
            <div class="footer">
                Este e-mail é gerado automaticamente pelo Módulo de Automações do Shopping Flamboyant.<br>
                Considere o meio ambiente antes de imprimir este e-mail.
            </div>
        </div>
    </body>
    </html>
    """

    gmail_scopes = ["https://www.googleapis.com/auth/gmail.send"]
    usuario_creds = _obter_credenciais_usuario(user_id, gmail_scopes)
    if usuario_creds:
        try:
            return _enviar_via_gmail_api(usuario_creds, destinatario, assunto, html_content)
        except HttpError as gmail_err:
            logger.error(f"Falha no Gmail API do usuario: {gmail_err}")
            return False
        except Exception as gmail_err:
            logger.warning(
                f"Falha ao enviar e-mail via Gmail API do usuario ({gmail_err})"
            )
            return False

    if user_id:
        logger.warning("user_id informado, mas nao ha credenciais Gmail válidas para esse usuario.")
        return False

    logger.warning("Nenhum user_id informado; envio por Gmail do usuario nao disponivel.")
    return False
