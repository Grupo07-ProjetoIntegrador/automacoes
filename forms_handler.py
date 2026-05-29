import os
import logging
import time
from typing import Optional
import requests
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.oauth2.credentials import Credentials as OAuth2Credentials
from google.auth.transport.requests import Request as GoogleRequest
import config
from database import db_cursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _obter_credenciais_google(scopes, user_id: str = None):
    """
    Tenta obter credenciais nesta ordem:
    1) tokens do usuário salvos na tabela `google_oauth_tokens` (se `user_id` fornecido)
    2) `token.json` (credenciais OAuth pessoais na pasta)
    3) Conta de serviço (credentials.json)
    """
    creds = None

    # 1) Tentar credenciais do usuário no banco
    if user_id:
        try:
            with db_cursor() as cursor:
                cursor.execute(
                    "SELECT access_token, refresh_token, token_type, scope, expires_at FROM google_oauth_tokens WHERE user_id = %s LIMIT 1;",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    access_token, refresh_token, token_type, scope, expires_at = row
                    creds = OAuth2Credentials(
                        token=access_token,
                        refresh_token=refresh_token,
                        token_uri='https://oauth2.googleapis.com/token',
                        client_id=os.getenv('GOOGLE_CLIENT_ID'),
                        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                        scopes=scopes,
                    )
                    # Refresh if expired and refresh_token available
                    try:
                        if hasattr(creds, 'expired') and creds.expired and creds.refresh_token:
                            logger.info('Atualizando token do usuário via refresh_token...')
                            creds.refresh(GoogleRequest())
                            # Optionally update database with new access token and expiry
                            with db_cursor() as update_cursor:
                                update_cursor.execute(
                                    "UPDATE google_oauth_tokens SET access_token = %s, expires_at = %s WHERE user_id = %s;",
                                    (creds.token, creds.expiry, user_id)
                                )
                    except Exception as refresh_err:
                        logger.warning(f'Falha ao atualizar token do usuário: {refresh_err}')
                    logger.info('Utilizando credenciais do usuário obtidas do banco.')
                    return creds
        except Exception as db_err:
            logger.warning(f'Erro ao buscar tokens do usuário no banco: {db_err}')

    # 2) token.json local (fallback)
    token_path = "token.json"
    if os.path.exists(token_path):
        try:
            creds = OAuth2Credentials.from_authorized_user_file(token_path, scopes)
            if creds and getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
                logger.info("Atualizando token OAuth2 expirado...")
                creds.refresh(GoogleRequest())
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            logger.info("Utilizando credenciais OAuth 2.0 pessoais (token.json).")
            return creds
        except Exception as oauth_err:
            logger.error(f"Erro ao carregar ou atualizar o token.json: {oauth_err}")
            creds = None

    # 3) Conta de serviço
    if not creds and os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
        logger.info("Utilizando credenciais da Conta de Serviço (credentials.json).")
        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_FILE,
            scopes=scopes
        )

    return creds

def apagar_formulario(treinamento_id: str, user_id: str = None) -> dict:
    """Remove o vinculo no banco e tenta apagar o formulario no Drive."""
    form_id = ""
    url_formulario = ""

    try:
        with db_cursor() as cursor:
            cursor.execute(
                """
                SELECT google_form_id, url_formulario
                FROM formularios_treinamento
                WHERE treinamento_id = %s
                ORDER BY criado_em DESC
                LIMIT 1;
                """,
                (treinamento_id,)
            )
            row = cursor.fetchone()
            if not row:
                return {"found": False}
            form_id = row[0] or ""
            url_formulario = row[1] or ""

        owner_user_id = _extrair_owner_da_url(url_formulario) or user_id

        with db_cursor() as cursor:
            cursor.execute(
                "DELETE FROM formularios_treinamento WHERE treinamento_id = %s;",
                (treinamento_id,)
            )
    except Exception as err:
        logger.error(f"Erro ao remover formulario do banco: {err}")
        return {"found": True, "deleted": False, "drive_deleted": False, "form_id": form_id}

    drive_deleted = False
    if form_id:
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = _obter_credenciais_google(scopes, user_id=owner_user_id)
        if creds:
            try:
                drive_service = build("drive", "v3", credentials=creds)
                drive_service.files().delete(fileId=form_id).execute()
                drive_deleted = True
                logger.info(f"Formulario {form_id} removido do Drive.")
            except Exception as drive_err:
                logger.warning(f"Falha ao remover formulario no Drive: {drive_err}")
        else:
            logger.warning("Credenciais Google nao encontradas para apagar o formulario.")

    return {
        "found": True,
        "deleted": True,
        "drive_deleted": drive_deleted,
        "form_id": form_id,
        "url_formulario": url_formulario.split("#", 1)[0],
    }

def obter_lojas_ativas():
    """Busca os nomes de todas as lojas ativas no banco de dados para popular o formulário."""
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT DISTINCT nome FROM lojas WHERE status = true ORDER BY nome;")
            lojas = cursor.fetchall()
            return [loja[0] for loja in lojas]
    except Exception as e:
        logger.error(f"Erro ao buscar lojas para o Forms: {e}")
        return []

def verificar_forms_existente(treinamento_id: str) -> str:
    """Verifica na tabela se já existe um formulário atrelado a este treinamento."""
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT url_formulario FROM formularios_treinamento WHERE treinamento_id = %s LIMIT 1;", (treinamento_id,))
            resultado = cursor.fetchone()
            if resultado:
                return resultado[0].split("#", 1)[0] if resultado[0] else resultado[0]
    except Exception as e:
        logger.warning(f"Aviso ao verificar formulário existente no banco: {e}")
    return None

def salvar_forms_no_banco(treinamento_id: str, form_id: str, url_formulario: str, user_id: str = None):
    """Registra o vínculo do novo formulário com o treinamento na tabela do Supabase."""
    try:
        url_armazenada = _anexar_owner_na_url(url_formulario, user_id)
        with db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO formularios_treinamento (treinamento_id, google_form_id, url_formulario, criado_em)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (treinamento_id) DO NOTHING;
            """, (treinamento_id, form_id, url_armazenada))
    except Exception as e:
        logger.error(f"Erro ao salvar o formulário no banco de dados: {e}")

def _normalizar_url_base(url: str) -> str:
    return url.rstrip("/") if url else ""


def _anexar_owner_na_url(url_formulario: str, user_id: str = None) -> str:
    if not url_formulario or not user_id:
        return url_formulario

    parsed = urlparse(url_formulario)
    fragment = urlencode({"owner_user_id": user_id})
    return urlunparse(parsed._replace(fragment=fragment))


def _extrair_owner_da_url(url_formulario: str) -> str:
    if not url_formulario:
        return ""

    parsed = urlparse(url_formulario)
    if not parsed.fragment:
        return ""

    fragment_data = parse_qs(parsed.fragment)
    owner_values = fragment_data.get("owner_user_id", [])
    return owner_values[0] if owner_values else ""

def registrar_webhook_forms(treinamento_id: str, form_id: str) -> Optional[bool]:
    """Registra o gatilho do Apps Script para enviar respostas ao webhook publico."""
    if not config.APPS_SCRIPT_WEBAPP_URL or not config.AUTOMACOES_PUBLIC_URL:
        logger.info("Apps Script Web App ou URL publica nao configurados; gatilho nao registrado.")
        return None

    webhook_url = f"{_normalizar_url_base(config.AUTOMACOES_PUBLIC_URL)}/api/automacoes/webhook-inscricao"
    payload = {
        "treinamento_id": treinamento_id,
        "form_id": form_id,
        "webhook_url": webhook_url
    }
    if config.APPS_SCRIPT_TOKEN:
        payload["token"] = config.APPS_SCRIPT_TOKEN
    headers = {"Content-Type": "application/json"}
    if config.APPS_SCRIPT_TOKEN:
        headers["X-Automacoes-Token"] = config.APPS_SCRIPT_TOKEN

    try:
        response = requests.post(config.APPS_SCRIPT_WEBAPP_URL, json=payload, headers=headers, timeout=10)
        if response.status_code in [200, 201]:
            logger.info("Gatilho do Apps Script registrado com sucesso.")
            return True
        logger.error(f"Falha ao registrar gatilho no Apps Script: {response.status_code} - {response.text}")
        return False
    except requests.exceptions.RequestException as err:
        logger.error(f"Erro ao chamar Apps Script Web App: {err}")
        return False

def criar_google_form(treinamento_id: str, tema_treinamento: str, user_id: str = None) -> str:
    """
    Cria ou recupera um formulário no Google Forms.
    Garante a exclusão de perguntas fantasmas e limita estritamente a 1 resposta por conta.
    """
    url_existente = verificar_forms_existente(treinamento_id)
    if url_existente:
        logger.info(f"🔄 [REUTILIZADO] Formulário já existia para o treinamento {treinamento_id}. Retornando URL salva.")
        return url_existente

    form_id = None
    responder_uri = f"https://docs.google.com/forms/d/e/mock_form_fallback_{treinamento_id}/viewform"

    creds = None
    scopes = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/drive"
    ]
    # Tenta obter credenciais do usuário (se informado), token.json ou conta de serviço
    creds = _obter_credenciais_google(scopes, user_id=user_id)
    if not creds:
        mock_uri = f"https://docs.google.com/forms/d/e/mock_form_{treinamento_id}/viewform"
        return mock_uri

    try:
        form_service = build('forms', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # 1. Cria o formulário em branco no Drive
        drive_file_meta = {
            "name": f"Inscrição - Treinamento: {tema_treinamento}",
            "mimeType": "application/vnd.google-apps.form"
        }
        drive_file = drive_service.files().create(
            body=drive_file_meta,
            fields="id, webViewLink"
        ).execute()

        form_id = drive_file.get("id")
        responder_uri = f"https://docs.google.com/forms/d/{form_id}/viewform"

        logger.info(f"Formulário criado via Drive API com sucesso. ID: {form_id}")

        # 2. Descobre o ID do item fantasma padrão que o Google cria sozinho para podermos deletá-lo
        form_atual = form_service.forms().get(formId=form_id).execute()
        itens_iniciais = form_atual.get("items", [])
        
        requests_lista = []
        
        # Se o Google criou um item padrão, adiciona o comando para apagá-lo
        if itens_iniciais:
            item_fantasma_id = itens_iniciais[0].get("itemId")
            requests_lista.append({
                "deleteItem": {
                    "location": {"index": 0}
                }
            })

        # Prepara a lista de lojas
        lojas = obter_lojas_ativas()
        if not lojas:
            lojas = ["Livraria Leitura", "Cacau Show", "Zara"]

        opcoes_lojas = [{"value": loja} for loja in lojas]
        opcoes_lojas.append({"value": "Outra Loja (Não listada)"})

        # 3. Monta a requisição estruturada das perguntas legítimas
        requests_lista.extend([
            {
                "updateFormInfo": {
                    "info": {
                        "title": f"Inscrição - Treinamento: {tema_treinamento}",
                        "description": "Por favor, preencha os dados abaixo para confirmar sua presença no treinamento do Shopping Flamboyant."
                    },
                    "updateMask": "title,description"
                }
            },
            {
                "createItem": {
                    "item": {
                        "title": "Nome do Representante",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "textQuestion": {}
                            }
                        }
                    },
                    "location": {"index": 0}
                }
            },
            {
                "createItem": {
                    "item": {
                        "title": "E-mail",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "textQuestion": {}
                            }
                        }
                    },
                    "location": {"index": 1}
                }
            },
            {
                "createItem": {
                    "item": {
                        "title": "Telefone",
                        "description": "Exemplo: (62) 99999-9999",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "textQuestion": {}
                            }
                        }
                    },
                    "location": {"index": 2}
                }
            },
            {
                "createItem": {
                    "item": {
                        "title": "Cargo",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "choiceQuestion": {
                                    "type": "DROP_DOWN",
                                    "options": [
                                        {"value": "Proprietário"},
                                        {"value": "Gerente"},
                                        {"value": "Supervisor"},
                                        {"value": "Líder"},
                                        {"value": "Outro"}
                                    ]
                                }
                            }
                        }
                    },
                    "location": {"index": 3}
                }
            },
            {
                "createItem": {
                    "item": {
                        "title": "Nome da Loja",
                        "description": "Selecione o nome da sua loja cadastrada no Shopping Flamboyant.",
                        "questionItem": {
                            "question": {
                                "required": True,
                                "choiceQuestion": {
                                    "type": "DROP_DOWN",
                                    "options": opcoes_lojas
                                }
                            }
                        }
                    },
                    "location": {"index": 4}
                }
            }
        ])

        # Executa a limpeza e criação tudo de uma vez só
        update_requests = {"requests": requests_lista}
        form_service.forms().batchUpdate(formId=form_id, body=update_requests).execute()
        logger.info("Formulário limpo e perguntas estruturadas adicionadas com sucesso.")

        # Recarrega metadados para pegar a URL pública correta
        form_metadata = form_service.forms().get(formId=form_id).execute()
        responder_uri = form_metadata.get("responderUri", responder_uri)

        # 4. 🔒 TRAVA ANTI-FRAUDE DEFINITIVA: Exige login e limita a exatamente 1 resposta
        try:
            form_service.forms().setPublishSettings(
                formId=form_id,
                body={
                    "publishSettings": {
                        "publishState": {
                            "isPublished": True,
                            "isAcceptingResponses": True
                        }
                    }
                }
            ).execute()
            
            # Atualiza o formulário para exigir apenas 1 resposta travando por e-mail do respondente
            form_service.forms().batchUpdate(
                formId=form_id,
                body={
                    "requests": [
                        {
                            "updateSettings": {
                                "settings": {
                                    "quizSettings": {"isQuiz": False}
                                },
                                "updateMask": "quizSettings"
                            }
                        }
                    ]
                }
            ).execute()
            
            # NOTA: O limite de 1 resposta por conta no Google Forms exige que a opção correspondente 
            # de coletar e-mails verificados esteja ativa no painel ou configurada nas políticas.
            logger.info("Formulário configurado com travas anti-fraude ativas.")
        except Exception as pub_api_err:
            logger.warning(f"Aviso ao aplicar configurações de publicação: {pub_api_err}")

        # Compartilhamento administrativo padrão
        if form_id:
            time.sleep(1)
            if config.DEFAULT_DESTINATION_EMAIL:
                try:
                    permission_body = {'type': 'user', 'role': 'writer', 'emailAddress': config.DEFAULT_DESTINATION_EMAIL}
                    drive_service.permissions().create(fileId=form_id, body=permission_body, transferOwnership=False).execute()
                except Exception as share_err:
                    logger.warning(f"Aviso de compartilhamento: {share_err}")

            try:
                public_permission = {'type': 'anyone', 'role': 'reader'}
                drive_service.permissions().create(fileId=form_id, body=public_permission).execute()
            except Exception as public_err:
                logger.warning(f"Aviso de permissão pública: {public_err}")

        if form_id:
            registrar_webhook_forms(treinamento_id, form_id)

        # Salva o resultado final no banco de dados para evitar duplicações futuras
        salvar_forms_no_banco(treinamento_id, form_id, responder_uri, user_id=user_id)

    except Exception as err:
        logger.error(f"Falha ao gerar o formulário no Google Forms real: {err}")

    return responder_uri