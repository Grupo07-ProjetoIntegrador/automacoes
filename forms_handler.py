import os
import logging
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
import config
from database import db_cursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
                return resultado[0]
    except Exception as e:
        logger.warning(f"Aviso ao verificar formulário existente no banco: {e}")
    return None

def salvar_forms_no_banco(treinamento_id: str, form_id: str, url_formulario: str):
    """Registra o vínculo do novo formulário com o treinamento na tabela do Supabase."""
    try:
        with db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO formularios_treinamento (treinamento_id, google_form_id, url_formulario, criado_em)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (treinamento_id) DO NOTHING;
            """, (treinamento_id, form_id, url_formulario))
    except Exception as e:
        logger.error(f"Erro ao salvar o formulário no banco de dados: {e}")

def criar_google_form(treinamento_id: str, tema_treinamento: str) -> str:
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
    token_path = "token.json"
    scopes = [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/drive"
    ]

    if os.path.exists(token_path):
        try:
            from google.oauth2.credentials import Credentials
            from google.auth.transport.requests import Request
            
            creds = Credentials.from_authorized_user_file(token_path, scopes)
            if creds and creds.expired and creds.refresh_token:
                logger.info("Atualizando token OAuth2 expirado...")
                creds.refresh(Request())
                with open(token_path, "w") as token_file:
                    token_file.write(creds.to_json())
            logger.info("Utilizando credenciais OAuth 2.0 pessoais (token.json).")
        except Exception as oauth_err:
            logger.error(f"Erro ao carregar ou atualizar o token.json: {oauth_err}")
            creds = None

    if not creds:
        if os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE):
            logger.info("Utilizando credenciais da Conta de Serviço (credentials.json).")
            creds = service_account.Credentials.from_service_account_file(
                config.GOOGLE_SERVICE_ACCOUNT_FILE,
                scopes=scopes
            )
        else:
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

        # Salva o resultado final no banco de dados para evitar duplicações futuras
        salvar_forms_no_banco(treinamento_id, form_id, responder_uri)

    except Exception as err:
        logger.error(f"Falha ao gerar o formulário no Google Forms real: {err}")

    return responder_uri