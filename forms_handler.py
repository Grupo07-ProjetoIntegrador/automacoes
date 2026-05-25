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
            cursor.execute("SELECT nome FROM lojas WHERE status = true ORDER BY nome;")
            lojas = cursor.fetchall()
            return [loja[0] for loja in lojas]
    except Exception as e:
        logger.error(f"Erro ao buscar lojas para o Forms: {e}")
        return []

def criar_google_form(treinamento_id: str, tema_treinamento: str) -> str:
    """
    Cria um formulário no Google Forms de forma 100% autônoma via Service Account.
    Mapeia as perguntas obrigatórias e popula o Dropdown de Lojas dinamicamente.
    Retorna a URL pública de resposta (responderUri).
    """
    # Inicializa as variáveis de retorno para evitar erros de escopo
    form_id = None
    responder_uri = f"https://docs.google.com/forms/d/e/mock_form_fallback_{treinamento_id}/viewform"

    # 1. Carrega as credenciais preferencialmente de token.json (OAuth2 pessoal) ou fallback para Conta de Serviço
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
            logger.warning(
                f"Nenhum arquivo de credenciais encontrado (token.json ou '{config.GOOGLE_SERVICE_ACCOUNT_FILE}'). "
                "Usando modo de SIMULAÇÃO para o Google Forms."
            )
            mock_uri = f"https://docs.google.com/forms/d/e/mock_form_{treinamento_id}/viewform"
            logger.info(f"[SIMULAÇÃO] Forms criado com sucesso para Treinamento '{tema_treinamento}'. Link: {mock_uri}")
            return mock_uri

    try:
        form_service = build('forms', 'v1', credentials=creds)
        drive_service = build('drive', 'v3', credentials=creds)

        # 3. Cria o formulário via Google Drive API (mimeType de Google Forms)
        # NOTA: A Forms API v1 não suporta criação direta via Service Account sem Domain-Wide Delegation.
        # A solução é criar o arquivo no Drive com o mimeType correto e depois usar o Forms API para editar.
        drive_file_meta = {
            "name": f"Inscrição - Treinamento: {tema_treinamento}",
            "mimeType": "application/vnd.google-apps.form"
        }
        drive_file = drive_service.files().create(
            body=drive_file_meta,
            fields="id, webViewLink"
        ).execute()

        form_id = drive_file.get("id")
        # Monta o link de resposta do Forms a partir do ID gerado pelo Drive
        responder_uri = f"https://docs.google.com/forms/d/{form_id}/viewform"

        logger.info(f"Formulário criado via Drive API com sucesso. ID: {form_id}")


        # 4. Busca lojas ativas no banco de dados
        lojas = obter_lojas_ativas()
        if not lojas:
            # Caso o banco esteja vazio, injeta dados fictícios para a API não quebrar (mínimo 2 opções)
            lojas = ["Livraria Leitura", "Cacau Show", "Zara"]

        # 5. Adiciona as perguntas ao formulário
        opcoes_lojas = [{"value": loja} for loja in lojas]
        opcoes_lojas.append({"value": "Outra Loja (Não listada)"})

        update_requests = {
            "requests": [
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
                },
                {
                    "createItem": {
                        "item": {
                            "title": "LUC da Loja",
                            "description": "Insira o código LUC identificador da sua loja no shopping.",
                            "questionItem": {
                                "question": {
                                    "required": True,
                                    "textQuestion": {}
                                }
                            }
                        },
                        "location": {"index": 5}
                    }
                }
            ]
        }

        form_service.forms().batchUpdate(formId=form_id, body=update_requests).execute()
        logger.info("Perguntas estruturadas adicionadas com sucesso ao Google Forms.")

        # 6. Obtém a URL pública real de resposta (responderUri) da Forms API
        form_metadata = form_service.forms().get(formId=form_id).execute()
        responder_uri = form_metadata.get("responderUri", responder_uri)
        logger.info(f"Link público de resposta oficial: {responder_uri}")

        # 6.5. Publica o formulário programaticamente para aceitar respostas
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
            logger.info("Formulário publicado ativamente e aceitando respostas via Forms API.")
        except Exception as pub_api_err:
            logger.warning(f"Aviso: Não foi possível publicar o formulário via Forms API ({pub_api_err})")

        # 7. Compartilha o Formulário com o administrador no Google Drive e torna público para respostas
        if form_id:
            time.sleep(2)
            # Compartilha com o e-mail do administrador
            if config.DEFAULT_DESTINATION_EMAIL:
                try:
                    permission_body = {
                        'type': 'user',
                        'role': 'writer',
                        'emailAddress': config.DEFAULT_DESTINATION_EMAIL
                    }
                    drive_service.permissions().create(
                        fileId=form_id,
                        body=permission_body,
                        transferOwnership=False
                    ).execute()
                    logger.info(f"Formulário compartilhado com permissão de escrita para: {config.DEFAULT_DESTINATION_EMAIL}")
                except Exception as share_err:
                    logger.warning(f"Aviso: Não foi possível compartilhar o arquivo no Drive ({share_err})")

            # Torna o formulário público (qualquer pessoa com o link pode responder/visualizar)
            try:
                public_permission = {
                    'type': 'anyone',
                    'role': 'reader'
                }
                drive_service.permissions().create(
                    fileId=form_id,
                    body=public_permission
                ).execute()
                logger.info("Formulário configurado com acesso público com sucesso (publicado).")
            except Exception as public_err:
                logger.warning(f"Aviso: Não foi possível tornar o formulário público automaticamente ({public_err})")

    except Exception as err:
        logger.error(f"Falha ao gerar o formulário no Google Forms real: {err}")
        logger.info(f"[FALLBACK] Retornando link simulado devido ao erro.")

    return responder_uri