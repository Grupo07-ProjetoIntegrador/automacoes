import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def enviar_email_formulario(tema_treinamento: str, link_formulario: str, email_destinatario: str = None) -> bool:
    """
    Dispara um e-mail HTML moderno contendo o link de inscrição para o treinamento.
    Caso as credenciais de SMTP estejam incompletas, simula o envio no log.
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
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Outfit', 'Inter', 'Helvetica Neue', Arial, sans-serif;
                background-color: #f3f4f6;
                margin: 0;
                padding: 0;
                color: #1f2937;
            }}
            .container {{
                max-width: 600px;
                margin: 40px auto;
                background-color: #ffffff;
                border-radius: 16px;
                overflow: hidden;
                box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
                border: 1px solid #e5e7eb;
            }}
            .header {{
                background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
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
                background-color: #eff6ff;
                border-left: 4px solid #3b82f6;
                padding: 15px;
                margin: 25px 0;
                border-radius: 0 8px 8px 0;
            }}
            .highlight-box strong {{
                color: #1e3a8a;
            }}
            .button-wrapper {{
                text-align: center;
                margin: 35px 0 15px 0;
            }}
            .btn {{
                background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
                color: #ffffff !important;
                text-decoration: none;
                padding: 14px 30px;
                font-size: 16px;
                font-weight: 600;
                border-radius: 30px;
                display: inline-block;
                box-shadow: 0 4px 6px -1px rgba(37, 99, 235, 0.2), 0 2px 4px -1px rgba(37, 99, 235, 0.1);
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

    # Verifica se os dados básicos de SMTP foram definidos no .env
    if not config.SMTP_EMAIL or not config.SMTP_PASSWORD:
        logger.warning(
            "Credenciais SMTP (SMTP_EMAIL/SMTP_PASSWORD) ausentes no .env. "
            "Simulando envio de e-mail..."
        )
        logger.info(f"[SIMULAÇÃO E-MAIL] De: sistema@flamboyant.com.br -> Para: {destinatario}")
        logger.info(f"[SIMULAÇÃO E-MAIL] Assunto: {assunto}")
        logger.info(f"[SIMULAÇÃO E-MAIL] Conteúdo do Link: {link_formulario}")
        return True

    try:
        # Monta a mensagem
        msg = MIMEMultipart('alternative')
        msg['Subject'] = assunto
        msg['From'] = config.SMTP_EMAIL
        msg['To'] = destinatario

        # Adiciona o HTML do e-mail
        msg.attach(MIMEText(html_content, 'html'))

        # Abre conexão com o servidor SMTP
        server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT)
        server.starttls()  # Upgrade da conexão para segura TLS
        server.login(config.SMTP_EMAIL, config.SMTP_PASSWORD)
        
        # Envia e-mail
        server.sendmail(config.SMTP_EMAIL, destinatario, msg.as_string())
        server.quit()

        logger.info(f"E-mail de convite enviado com sucesso para: {destinatario}")
        return True
    except Exception as e:
        logger.error(f"Falha ao enviar e-mail via SMTP real: {e}")
        return False
