import base64
import logging
import os
import smtplib
from datetime import datetime
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


def _obter_logo_base64_local() -> str:
    """
    Busca o arquivo de imagem local e converte para Base64.
    Se o arquivo não existir, retorna um fallback ou string vazia para não quebrar o sistema.
    """
    caminho_logo = os.path.join(os.path.dirname(__file__), "flamboyant-logo.png")
    
    if os.path.exists(caminho_logo):
        try:
            with open(caminho_logo, "rb") as image_file:
                encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
                return f"data:image/png;base64,{encoded_string}"
        except Exception as e:
            logger.error(f"Erro ao ler o arquivo de logo local: {e}")
    
    logger.warning("Arquivo 'flamboyant-logo.png' nao encontrado. O e-mail sera gerado sem a logo.")
    return ""


def _valor_treinamento(treinamento, chave: str, default: str = "") -> str:
    if treinamento is None:
        return default

    if isinstance(treinamento, dict):
        valor = treinamento.get(chave, default)
    else:
        valor = getattr(treinamento, chave, default)

    if valor is None:
        return default

    return str(valor).strip() or default


def _formatar_data_pt(data_iso: str) -> str:
    if not data_iso:
        return ""

    try:
        data = datetime.strptime(data_iso, "%Y-%m-%d")
    except ValueError:
        return data_iso

    meses = [
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    ]
    return f"{data.day} de {meses[data.month - 1]} de {data.year}"


def _formatar_periodo(treinamento) -> str:
    data = _formatar_data_pt(_valor_treinamento(treinamento, "data"))
    horario_inicio = _valor_treinamento(treinamento, "horario_inicio")
    horario_fim = _valor_treinamento(treinamento, "horario_fim")

    if horario_inicio and horario_fim:
        return f"{data}<br>Horário: das {horario_inicio} às {horario_fim}"
    if data:
        return f"{data}"
    return ""


def _compor_html_convite(treinamento, link_formulario: str, nome_destinatario: str = "") -> str:
    tema = _valor_treinamento(treinamento, "tema", "Treinamento")
    descricao = _valor_treinamento(treinamento, "descricao")
    objetivo = _valor_treinamento(treinamento, "objetivo")
    local = _valor_treinamento(treinamento, "local")
    segmento = _valor_treinamento(treinamento, "segmento_alvo")
    periodo = _formatar_periodo(treinamento)

    saudacao = f"Olá, {nome_destinatario}," if nome_destinatario else "Olá, Parceiro Lojista,"
    logo_src = _obter_logo_base64_local()

    linhas_detalhes = []
    if periodo:
        linhas_detalhes.append(f'<tr><td style="padding: 6px 0; font-weight: 700; color: #1F2937; width: 110px; vertical-align: top;">Data/Horário:</td><td style="padding: 6px 0; color: #4B5563; vertical-align: top;">{periodo}</td></tr>')
    if local:
        linhas_detalhes.append(f'<tr><td style="padding: 6px 0; font-weight: 700; color: #1F2937; vertical-align: top;">Local:</td><td style="padding: 6px 0; color: #4B5563; vertical-align: top;">{local}</td></tr>')
    if segmento:
        linhas_detalhes.append(f'<tr><td style="padding: 6px 0; font-weight: 700; color: #1F2937; vertical-align: top;">Público-Alvo:</td><td style="padding: 6px 0; color: #4B5563; vertical-align: top;">{segmento}</td></tr>')
    
    linhas_detalhes.append(f'<tr><td style="padding: 6px 0; font-weight: 700; color: #1F2937; vertical-align: top;">Inscrição:</td><td style="padding: 6px 0; vertical-align: top;"><span style="display: inline-block; background-color: rgba(16, 185, 129, 0.15); color: #10B981; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 700;">Obrigatória</span></td></tr>')

    tabela_detalhes_html = f'<table style="width: 100%; border-collapse: collapse; font-size: 14px;">{"".join(linhas_detalhes)}</table>'

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Convite de Treinamento - JP Mall Corporativo</title>
</head>
<body style="font-family: 'Inter', 'Roboto', system-ui, sans-serif; background-color: #F7F4EF; margin: 0; padding: 40px 20px; color: #1F2937; -webkit-print-color-adjust: exact;">
    <div style="max-width: 650px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);">
        
        <div style="background-color: #8B1A1A; padding: 30px 35px; border-bottom: 4px solid #C8A882;">
            <table style="width: 100%; border-collapse: collapse; border: 0;">
                <tr>
                    <td style="padding: 0; vertical-align: middle; text-align: left; width: 140px;">
                        {"<img src='" + logo_src + "' alt='Logo Flamboyant' style='display: block; width: 130px; height: auto; border: 0;' />" if logo_src else ""}
                    </td>
                    <td style="padding: 0; vertical-align: middle; text-align: right;">
                        <div style="color: #C8A882; text-transform: uppercase; font-size: 11px; letter-spacing: 1.5px; font-weight: 700; margin-bottom: 4px;">JP Mall Corporativo</div>
                        <h1 style="margin: 0; color: #FFFFFF; font-size: 20px; font-weight: 700; line-height: 1.3;">Desenvolvimento & Excelência:<br>Convite de Treinamento</h1>
                    </td>
                </tr>
            </table>
        </div>

        <div style="padding: 40px; line-height: 1.6;">
            <div style="font-size: 17px; font-weight: 700; color: #1F2937; margin-bottom: 16px;">{saudacao}</div>
            
            <p style="color: #4B5563; font-size: 15px; margin-top: 0; margin-bottom: 16px; text-align: justify;">
                Como parte do nosso compromisso contínuo em <em>elevar para evoluir e envolver para encantar</em>, convidamos sua equipe para participar do treinamento estratégico: <strong>{tema}</strong>.
            </p>

            {"<p style='color: #4B5563; font-size: 15px; margin-bottom: 16px; text-align: justify;'>" + descricao + "</p>" if descricao else ""}
            {"<p style='color: #4B5563; font-size: 15px; margin-bottom: 16px;'><strong>Objetivo:</strong> " + objetivo + "</p>" if objetivo else ""}

            <div style="background-color: #F7F4EF; border-left: 4px solid #8B1A1A; padding: 20px; margin: 25px 0; border-radius: 0 8px 8px 0;">
                <h3 style="margin-top: 0; margin-bottom: 12px; color: #8B1A1A; font-size: 14px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;">Informações do Evento</h3>
                {tabela_detalhes_html}
            </div>

            <p style="color: #4B5563; font-size: 15px; margin-bottom: 20px;">
                As vagas são limitadas para garantir a qualidade da interação. Clique no botão abaixo para preencher o formulário de inscrição oficial e garantir a presença dos seus colaboradores.
            </p>

            <div style="text-align: center; margin: 35px 0 10px 0;">
                <a href="{link_formulario}" style="display: inline-block; background-color: #D93030; color: #FFFFFF !important; text-decoration: none; padding: 14px 32px; font-weight: 700; font-size: 14px; border-radius: 6px; text-transform: uppercase; letter-spacing: 0.5px; box-shadow: 0 2px 4px rgba(217, 48, 48, 0.2);" target="_blank">Acessar Formulário de Inscrição</a>
            </div>
        </div>

        <div style="background-color: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 30px 40px; text-align: center;">
            <div style="font-size: 16px; font-weight: 700; color: #8B1A1A; letter-spacing: 1px; margin-bottom: 6px;">GRUPO FLAMBOYANT</div>
            <div style="font-size: 12px; font-style: italic; color: #C8A882; margin-bottom: 15px;">Elevar para evoluir, envolver para encantar.</div>
            <div style="font-size: 11px; color: #9CA3AF; line-height: 1.4;">
                Este é um comunicado oficial automatizado enviado pela Administration do JP Mall Corporativo.<br>
                © {datetime.now().year} Grupo Flamboyant — Todos os direitos reservados.
            </div>
        </div>
    </div>
</body>
</html>"""


def _compor_html_validacao_presenca(treinamento, nome_destinatario: str = "") -> str:
    tema = _valor_treinamento(treinamento, "tema", "Treinamento")
    local = _valor_treinamento(treinamento, "local")
    periodo = _formatar_periodo(treinamento)
    saudacao = f"Olá, {nome_destinatario}," if nome_destinatario else "Olá,"

    logo_src = _obter_logo_base64_local()

    linhas_evento = []
    if periodo:
        linhas_evento.append(f'<tr><td style="padding: 4px 0; font-weight: 700; color: #1F2937; width: 60px;">Data:</td><td style="padding: 4px 0; color: #4B5563;">{periodo}</td></tr>')
    if local:
        linhas_evento.append(f'<tr><td style="padding: 4px 0; font-weight: 700; color: #1F2937;">Local:</td><td style="padding: 4px 0; color: #4B5563;">{local}</td></tr>')

    tabela_evento_html = f'<table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 10px;">{"".join(linhas_evento)}</table>' if linhas_evento else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Presença Confimada - JP Mall Corporativo</title>
</head>
<body style="font-family: 'Inter', 'Roboto', system-ui, sans-serif; background-color: #F7F4EF; margin: 0; padding: 40px 20px; color: #1F2937; -webkit-print-color-adjust: exact;">
    <div style="max-width: 650px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);">
        
        <div style="background-color: #8B1A1A; padding: 30px 35px; border-bottom: 4px solid #C8A882;">
            <table style="width: 100%; border-collapse: collapse; border: 0;">
                <tr>
                    <td style="padding: 0; vertical-align: middle; text-align: left; width: 140px;">
                        {"<img src='" + logo_src + "' alt='Logo Flamboyant' style='display: block; width: 130px; height: auto; border: 0;' />" if logo_src else ""}
                    </td>
                    <td style="padding: 0; vertical-align: middle; text-align: right;">
                        <div style="color: #C8A882; text-transform: uppercase; font-size: 12px; letter-spacing: 2px; font-weight: 700; margin-bottom: 4px;">JP Mall Corporativo</div>
                        <h1 style="margin: 0; color: #FFFFFF; font-size: 22px; font-weight: 700; line-height: 1.3;">Presença Validada com Sucesso</h1>
                    </td>
                </tr>
            </table>
        </div>

        <div style="padding: 40px; line-height: 1.6;">
            <div style="font-size: 17px; font-weight: 700; color: #1F2937; margin-bottom: 16px;">{saudacao}</div>
            
            <p style="color: #4B5563; font-size: 15px; margin-top: 0; margin-bottom: 16px;">
                Sua participação foi registrada e validada com sucesso no sistema para o treinamento <strong>{tema}</strong>.
            </p>
            
            <p style="color: #4B5563; font-size: 15px; margin-bottom: 16px;">
                Agradecemos o seu empenho e dedicação em evoluir suas competências junto ao ecossistema do shopping. Caso queira consultar, seguem abaixo as informações registradas da sessão:
            </p>

            {f'<div style="background-color: #F9FAFB; border: 1px solid #E5E7EB; padding: 20px; margin: 20px 0; border-radius: 8px;"><h4 style="margin: 0; color: #8B1A1A; font-size: 14px; font-weight: 700; text-transform: uppercase;">Dados da Sessão</h4>{tabela_evento_html}</div>' if tabela_evento_html else ""}

            <p style="color: #4B5563; font-size: 15px; margin-top: 20px; margin-bottom: 0;">
                Obrigado por sua valiosa participação e contribuição com a cultura de capacitação e excelência do Grupo Flamboyant.
            </p>
        </div>

        <div style="background-color: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 30px 40px; text-align: center;">
            <div style="font-size: 16px; font-weight: 700; color: #8B1A1A; letter-spacing: 1px; margin-bottom: 6px;">GRUPO FLAMBOYANT</div>
            <div style="font-size: 12px; font-style: italic; color: #C8A882; margin-bottom: 15px;">Elevar para evoluir, envolver para encantar.</div>
            <div style="font-size: 11px; color: #9CA3AF; line-height: 1.4;">
                Este e-mail confirma a presença registrada de forma oficial no ecossistema do Shopping Flamboyant.<br>
                © {datetime.now().year} Grupo Flamboyant — Todos os direitos reservados.
            </div>
        </div>
    </div>
</body>
</html>"""


def _enviar_via_smtp(destinatario: str, assunto: str, html_content: str) -> bool:
    smtp_server = config.SMTP_SERVER
    smtp_port = config.SMTP_PORT
    smtp_email = config.SMTP_EMAIL
    smtp_password = config.SMTP_PASSWORD

    if not smtp_email or not smtp_password:
        logger.warning("Credenciais SMTP ausentes; envio por SMTP indisponível.")
        return False

    message = MIMEMultipart("alternative")
    message["From"] = smtp_email
    message["To"] = destinatario
    message["Subject"] = assunto
    message.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, [destinatario], message.as_string())
        return True
    except Exception as err:
        logger.error(f"Falha no envio via SMTP: {err}")
        return False


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


def _enviar_via_gmail_api(gmail_service, destinatario: str, assunto: str, html_content: str) -> bool:
    """Modificado para aceitar o 'gmail_service' já instanciado de fora e evitar builds repetitivos"""
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
    treinamento,
    link_formulario: str,
    email_destinatario: str = None,
    user_id: str = None,
    nome_destinatario: str = "",
    usuario_creds=None,  # AJUSTE DA MUDANÇA 3: Injetável de fora
) -> bool:
    destinatario = email_destinatario or config.DEFAULT_DESTINATION_EMAIL
    
    if not destinatario:
        logger.warning("Nenhum e-mail de destino configurado ou fornecido. O e-mail não será enviado.")
        return False

    tema_treinamento = _valor_treinamento(treinamento, "tema", "Treinamento")
    assunto = f"Inscrições Abertas: Treinamento - {tema_treinamento}"
    html_content = _compor_html_convite(treinamento, link_formulario, nome_destinatario=nome_destinatario)

    # Se as credenciais não forem injetadas, executa o fluxo padrão de busca no banco
    if not usuario_creds:
        if not user_id:
            user_id = os.getenv("GOOGLE_MASTER_USER_ID")

        gmail_scopes = ["https://www.googleapis.com/auth/gmail.send"]
        usuario_creds = _obter_credenciais_usuario(user_id, gmail_scopes)

    if usuario_creds:
        try:
            # Constrói o serviço apenas uma vez por chamada de envio
            gmail_service = build("gmail", "v1", credentials=usuario_creds)
            return _enviar_via_gmail_api(gmail_service, destinatario, assunto, html_content)
        except HttpError as gmail_err:
            logger.error(f"Falha no Gmail API do usuario: {gmail_err}")
        except Exception as gmail_err:
            logger.warning(f"Falha ao enviar e-mail via Gmail API do usuario ({gmail_err})")

    logger.warning("Fazendo fallback para SMTP para envio do e-mail de convite.")
    return _enviar_via_smtp(destinatario, assunto, html_content)


def enviar_email_validacao_presenca(
    treinamento,
    email_destinatario: str,
    nome_destinatario: str = "",
    user_id: str = None,
    usuario_creds=None,  # AJUSTE DA MUDANÇA 3: Injetável de fora
) -> bool:
    destinatario = email_destinatario or config.DEFAULT_DESTINATION_EMAIL
    if not destinatario:
        logger.warning("Nenhum e-mail de destino configurado para a validação de presença.")
        return False

    assunto = f"Presença validada: { _valor_treinamento(treinamento, 'tema', 'Treinamento') }"
    html_content = _compor_html_validacao_presenca(treinamento, nome_destinatario=nome_destinatario)

    # Se as credenciais não forem injetadas, executa o fluxo padrão de busca no banco
    if not usuario_creds:
        if not user_id:
            user_id = os.getenv("GOOGLE_MASTER_USER_ID")
            logger.info(f"Nenhum user_id fornecido para o check-in. Utilizando fallback da Conta Master ID: {user_id}")

        gmail_scopes = ["https://www.googleapis.com/auth/gmail.send"]
        usuario_creds = _obter_credenciais_usuario(user_id, gmail_scopes)

    if usuario_creds:
        try:
            # Constrói o serviço apenas uma vez por chamada de envio
            gmail_service = build("gmail", "v1", credentials=usuario_creds)
            return _enviar_via_gmail_api(gmail_service, destinatario, assunto, html_content)
        except HttpError as gmail_err:
            logger.error(f"Falha de API do Gmail ao enviar confirmação de presença: {gmail_err.content.decode('utf-8')}")
        except Exception as gmail_err:
            logger.warning(f"Falha crítica ao enviar validação via Gmail API ({gmail_err})")

    logger.warning("Fazendo fallback para SMTP para envio do e-mail de presença validada.")
    return _enviar_via_smtp(destinatario, assunto, html_content)


def _compor_html_confirmacao_inscricao(treinamento, nome_destinatario: str = "") -> str:
    tema = _valor_treinamento(treinamento, "tema", "Treinamento")
    local = _valor_treinamento(treinamento, "local")
    periodo = _formatar_periodo(treinamento)
    saudacao = f"Olá, {nome_destinatario}," if nome_destinatario else "Olá,"

    logo_src = _obter_logo_base64_local()

    linhas_evento = []
    if periodo:
        linhas_evento.append(f'<tr><td style="padding: 4px 0; font-weight: 700; color: #1F2937; width: 60px;">Data:</td><td style="padding: 4px 0; color: #4B5563;">{periodo}</td></tr>')
    if local:
        linhas_evento.append(f'<tr><td style="padding: 4px 0; font-weight: 700; color: #1F2937;">Local:</td><td style="padding: 4px 0; color: #4B5563;">{local}</td></tr>')

    tabela_evento_html = f'<table style="width: 100%; border-collapse: collapse; font-size: 14px; margin-top: 10px;">{"".join(linhas_evento)}</table>' if linhas_evento else ""

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8">
    <title>Inscrição Confirmada - JP Mall Corporativo</title>
</head>
<body style="font-family: 'Inter', 'Roboto', system-ui, sans-serif; background-color: #F7F4EF; margin: 0; padding: 40px 20px; color: #1F2937; -webkit-print-color-adjust: exact;">
    <div style="max-width: 650px; margin: 0 auto; background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05);">
        
        <div style="background-color: #8B1A1A; padding: 30px 35px; border-bottom: 4px solid #C8A882;">
            <table style="width: 100%; border-collapse: collapse; border: 0;">
                <tr>
                    <td style="padding: 0; vertical-align: middle; text-align: left; width: 140px;">
                        {"<img src='" + logo_src + "' alt='Logo Flamboyant' style='display: block; width: 130px; height: auto; border: 0;' />" if logo_src else ""}
                    </td>
                    <td style="padding: 0; vertical-align: middle; text-align: right;">
                        <div style="color: #C8A882; text-transform: uppercase; font-size: 12px; letter-spacing: 2px; font-weight: 700; margin-bottom: 4px;">JP Mall Corporativo</div>
                        <h1 style="margin: 0; color: #FFFFFF; font-size: 22px; font-weight: 700; line-height: 1.3;">Sua Inscrição foi Confirmada!</h1>
                    </td>
                </tr>
            </table>
        </div>

        <div style="padding: 40px; line-height: 1.6;">
            <div style="font-size: 17px; font-weight: 700; color: #1F2937; margin-bottom: 16px;">{saudacao}</div>
            
            <p style="color: #4B5563; font-size: 15px; margin-top: 0; margin-bottom: 16px;">
                Sua inscrição para o treinamento <strong>{tema}</strong> foi realizada com sucesso!
            </p>
            
            <p style="color: #4B5563; font-size: 15px; margin-bottom: 16px;">
                Ficamos muito felizes com sua participação. Abaixo estão as informações do treinamento para você se programar:
            </p>

            {f'<div style="background-color: #F9FAFB; border: 1px solid #E5E7EB; padding: 20px; margin: 20px 0; border-radius: 8px;"><h4 style="margin: 0; color: #8B1A1A; font-size: 14px; font-weight: 700; text-transform: uppercase;">Detalhes do Treinamento</h4>{tabela_evento_html}</div>' if tabela_evento_html else ""}

            <p style="color: #4B5563; font-size: 15px; margin-top: 20px; margin-bottom: 0;">
                Prepare-se para uma excelente jornada de aprendizado. Nos vemos no treinamento!
            </p>
        </div>

        <div style="background-color: #F9FAFB; border-top: 1px solid #E5E7EB; padding: 30px 40px; text-align: center;">
            <div style="font-size: 16px; font-weight: 700; color: #8B1A1A; letter-spacing: 1px; margin-bottom: 6px;">GRUPO FLAMBOYANT</div>
            <div style="font-size: 12px; font-style: italic; color: #C8A882; margin-bottom: 15px;">Elevar para evoluir, envolver para encantar.</div>
            <div style="font-size: 11px; color: #9CA3AF; line-height: 1.4;">
                Este e-mail confirma a inscrição recebida de forma oficial no ecossistema do Shopping Flamboyant.<br>
                © {datetime.now().year} Grupo Flamboyant — Todos os direitos reservados.
            </div>
        </div>
    </div>
</body>
</html>"""


def enviar_email_confirmacao_inscricao(
    treinamento,
    email_destinatario: str,
    nome_destinatario: str = "",
    user_id: str = None,
    usuario_creds=None,
) -> bool:
    destinatario = email_destinatario or config.DEFAULT_DESTINATION_EMAIL
    if not destinatario:
        logger.warning("Nenhum e-mail de destino configurado para a confirmação de inscrição.")
        return False

    assunto = f"Inscrição Confirmada: { _valor_treinamento(treinamento, 'tema', 'Treinamento') }"
    html_content = _compor_html_confirmacao_inscricao(treinamento, nome_destinatario=nome_destinatario)

    if not usuario_creds:
        if not user_id:
            user_id = os.getenv("GOOGLE_MASTER_USER_ID")
            logger.info(f"Nenhum user_id fornecido. Utilizando fallback da Conta Master ID: {user_id}")

        gmail_scopes = ["https://www.googleapis.com/auth/gmail.send"]
        usuario_creds = _obter_credenciais_usuario(user_id, gmail_scopes)

    if usuario_creds:
        try:
            gmail_service = build("gmail", "v1", credentials=usuario_creds)
            return _enviar_via_gmail_api(gmail_service, destinatario, assunto, html_content)
        except HttpError as gmail_err:
            logger.error(f"Falha de API do Gmail ao enviar confirmação de inscrição: {gmail_err.content.decode('utf-8')}")
        except Exception as gmail_err:
            logger.warning(f"Falha crítica ao enviar confirmação via Gmail API ({gmail_err})")

    logger.warning("Fazendo fallback para SMTP para envio do e-mail de confirmação de inscrição.")
    return _enviar_via_smtp(destinatario, assunto, html_content)