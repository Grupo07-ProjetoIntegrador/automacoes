import os
import logging
import time
from datetime import datetime, timezone
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
    dias = [
        "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo",
    ]
    return f"{data.day} de {meses[data.month - 1]} ({dias[data.weekday()]})"


def _montar_descricao_forms(treinamento) -> str:
    descricao = _valor_treinamento(treinamento, "descricao")
    objetivo = _valor_treinamento(treinamento, "objetivo")
    data = _formatar_data_pt(_valor_treinamento(treinamento, "data"))
    horario_inicio = _valor_treinamento(treinamento, "horario_inicio")
    horario_fim = _valor_treinamento(treinamento, "horario_fim")
    local = _valor_treinamento(treinamento, "local")
    segmento = _valor_treinamento(treinamento, "segmento_alvo")

    partes = []
    if descricao:
        partes.append(descricao)
    if objetivo:
        partes.append(f"Objetivo: {objetivo}")
    if data or horario_inicio or horario_fim:
        if horario_inicio and horario_fim:
            partes.append(f"Data: {data}\nHorário: das {horario_inicio} às {horario_fim}")
        else:
            partes.append(f"Data: {data}")
    if local:
        partes.append(f"Local: {local}")
    if segmento:
        partes.append(f"Segmento-alvo: {segmento}")

    return "\n\n".join(parte for parte in partes if parte).strip()


def _obter_credenciais_google(scopes, user_id: str = None):
    """
    Tenta obter credenciais nesta ordem:
    1) tokens do usuário salvos na tabela `google_oauth_tokens` (se `user_id` fornecido)
    2) token.json (credenciais OAuth pessoais na pasta)
    3) Conta de serviço (credentials.json)
    
    Adicionado: Renovação automática permanente (Auto-refresh) salvando de volta no Supabase.
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

                    # Garante que expires_at seja timezone-aware (UTC) para que
                    # creds.expired funcione corretamente na comparação de datas
                    if expires_at and isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)

                    creds = OAuth2Credentials(
                        token=access_token,
                        refresh_token=refresh_token,
                        token_uri='https://oauth2.googleapis.com/token',
                        client_id=os.getenv('GOOGLE_CLIENT_ID'),
                        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                        scopes=scopes,
                        expiry=expires_at,  # CORREÇÃO: sem isso, creds.expired é sempre False
                    )
                    
                    # Verifica se o token expirou (ou está prestes a expirar) e faz o Auto-Refresh
                    if hasattr(creds, 'expired') and creds.expired and creds.refresh_token:
                        try:
                            logger.info(f"🔄 Token do usuário {user_id} expirado no Supabase. Executando renovação via Refresh Token...")
                            creds.refresh(GoogleRequest())
                            
                            # Formata a nova expiração gerada pelo Google para salvar corretamente no PostgreSQL
                            nova_expiracao = creds.expiry.strftime('%Y-%m-%d %H:%M:%S') if creds.expiry else None
                            
                            # PERSISTÊNCIA: Atualiza imediatamente o Supabase com o novo access_token válido por mais 1 hora
                            with db_cursor() as update_cursor:
                                update_cursor.execute(
                                    "UPDATE google_oauth_tokens SET access_token = %s, expires_at = %s WHERE user_id = %s;",
                                    (creds.token, nova_expiracao, user_id)
                                )
                            logger.info(f"✅ Novo access_token do usuário {user_id} persistido com sucesso no Supabase!")
                        except Exception as refresh_err:
                            logger.warning(f"Falha ao renovar token do usuário {user_id} em background: {refresh_err}")
                    
                    logger.info(f"Utilizando credenciais do usuário {user_id} obtidas do banco.")
                    return creds
        except Exception as db_err:
            logger.warning(f"Erro ao buscar ou atualizar tokens do usuário no banco: {db_err}")

    # 2) token.json local (fallback para ambiente de desenvolvimento local)
    token_path = "token.json"
    if os.path.exists(token_path):
        try:
            creds = OAuth2Credentials.from_authorized_user_file(token_path, scopes)
            if creds and getattr(creds, 'expired', False) and getattr(creds, 'refresh_token', None):
                logger.info("Atualizando token OAuth2 local (token.json) expirado...")
                creds.refresh(GoogleRequest())
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            logger.info("Utilizando credenciais OAuth 2.0 pessoais locais (token.json).")
            return creds
        except Exception as oauth_err:
            logger.error(f"Erro ao carregar ou atualizar o token.json: {oauth_err}")
            creds = None

    # 3) Conta de serviço (Fallback institucional padrão)
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
                drive_service = None
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


def registrar_webhook_forms(treinamento_id: str, form_id: str, user_id: str = None) -> Optional[bool]:
    """
    Registra o gatilho do Apps Script enviando uma chamada direta para o Web App estável.
    Removida a requisição de atualização de infraestrutura/deploy via API do Google Script para evitar erros de 401.
    """
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
        logger.info(f"Disparando requisição de vinculação de Gatilho para o Apps Script Web App estável...")
        response = requests.post(config.APPS_SCRIPT_WEBAPP_URL, json=payload, headers=headers, timeout=30)
        if response.status_code in [200, 201]:
            logger.info("Gatilho do Apps Script registrado com sucesso.")
            return True
        logger.error(f"Falha ao registrar gatilho no Apps Script: {response.status_code} - {response.text}")
        return False
    except requests.exceptions.RequestException as err:
        logger.error(f"Erro ao chamar Apps Script Web App: {err}")
        return False


def criar_google_form(treinamento_id: str, treinamento, user_id: str = None) -> str:
    """
    Cria ou recupera um formulário no Google Forms.
    Garante a exclusão de perguntas fantasmas e limita estritamente a 1 resposta por conta.
    """
    tema_treinamento = _valor_treinamento(treinamento, "tema", "Treinamento")
    url_existente = verificar_forms_existente(treinamento_id)
    if url_existente:
        logger.info(f"🔄 [REUTILIZADO] Formulário já existia para o treinamento {treinamento_id}. Retornando URL salva.")
        return url_existente

    form_id = None
    responder_uri = f"https://docs.google.com/forms/d/e/mock_form_fallback_{treinamento_id}/viewform"

    scopes = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/drive"
    ]
    
    creds = _obter_credenciais_google(scopes, user_id=user_id)
    if not creds:
        mock_uri = f"https://docs.google.com/forms/d/e/mock_form_{treinamento_id}/viewform"
        return mock_uri

    try:
        form_service = build('forms', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

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

        form_atual = form_service.forms().get(formId=form_id).execute()
        itens_iniciais = form_atual.get("items", [])
        
        requests_lista = []
        
        if itens_iniciais:
            requests_lista.append({
                "deleteItem": {
                    "location": {"index": 0}
                }
            })

        lojas_raw = obter_lojas_ativas()
        if not lojas_raw:
            lojas_raw = ["Livraria Leitura", "Cacau Show", "Zara"]
        seen = set()
        lojas = []
        for nome in lojas_raw:
            chave = nome.strip().upper()
            if chave not in seen:
                seen.add(chave)
                lojas.append(nome)

        opcoes_lojas = [{"value": loja} for loja in lojas]
        opcoes_lojas.append({"value": "Outra Loja (Não listada)"})

        requests_lista.extend([
            {
                "updateFormInfo": {
                    "info": {
                        "title": f"Inscrição - Treinamento: {tema_treinamento}",
                        "description": _montar_descricao_forms(treinamento) or "Por favor, preencha os dados abaixo para confirmar sua presença no treinamento do Shopping Flamboyant."
                    },
                    "updateMask": "title,description"
                }
            }
        ])
        
        # Adiciona os campos de perguntas estritamente no formato batch
        perguntas = ["Nome do Representante", "E-mail", "Telefone"]
        for idx, titulo_pergunta in enumerate(perguntas):
            item_data = {
                "createItem": {
                    "item": {
                        "title": titulo_pergunta,
                        "questionItem": {
                            "question": {
                                "required": True,
                                "textQuestion": {}
                            }
                        }
                    },
                    "location": {"index": idx}
                }
            }
            if titulo_pergunta == "Telefone":
                item_data["createItem"]["item"]["description"] = "Exemplo: (62) 99999-9999"
            requests_lista.append(item_data)

        requests_lista.extend([
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

        update_requests = {"requests": requests_lista}
        form_service.forms().batchUpdate(formId=form_id, body=update_requests).execute()
        logger.info("Formulário limpo e perguntas estruturadas adicionadas com sucesso.")

        form_metadata = form_service.forms().get(formId=form_id).execute()
        responder_uri = form_metadata.get("responderUri", responder_uri)

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
            
            logger.info("Formulário configurado com travas anti-fraude ativas.")
        except Exception as pub_api_err:
            logger.warning(f"Aviso ao aplicar configurações de publicação: {pub_api_err}")

        if form_id:
            time.sleep(1)
            if config.DEFAULT_DESTINATION_EMAIL:
                try:
                    permission_body = {'type': 'user', 'role': 'writer', 'emailAddress': config.DEFAULT_DESTINATION_EMAIL}
                    drive_service.permissions().create(fileId=form_id, body=permission_body, transferOwnership=False).execute()
                except Exception as share_err:
                    if "server closed the connection unexpectedly" in str(share_err):
                         logger.warning("Banco de dados fechou a conexao, ignorando erro menor de permissao.")
                    else:
                         logger.warning(f"Aviso de compartilhamento: {share_err}")

            try:
                public_permission = {'type': 'anyone', 'role': 'reader'}
                drive_service.permissions().create(fileId=form_id, body=public_permission).execute()
            except Exception as public_err:
                logger.warning(f"Aviso de permissão pública: {public_err}")

        if form_id:
            registrar_webhook_forms(treinamento_id, form_id, user_id=user_id)

        salvar_forms_no_banco(treinamento_id, form_id, responder_uri, user_id=user_id)

    except Exception as err:
        logger.error(f"Falha ao gerar o formulário no Google Forms real: {err}")

    return responder_uri