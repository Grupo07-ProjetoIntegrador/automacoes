import os
import json
from datetime import datetime, timedelta
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Importa o cursor do banco de dados do seu projeto
from database import db_cursor

# TODOS OS ESCOPOS QUE O SEU SISTEMA EXIGE
SCOPES = [
    "https://www.googleapis.com/auth/forms.body",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.scriptapp",
    "https://www.googleapis.com/auth/script.external_request",
    "https://www.googleapis.com/auth/forms",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.deployments"
]

def salvar_token_no_banco(user_id: str, creds):
    """
    Grava ou atualiza as credenciais na tabela utilizada pelo email_service.py
    """
    # Calcula uma data de expiração caso ela venha vazia do objeto creds
    expires_at = creds.expiry if creds.expiry else (datetime.now() + timedelta(seconds=3600))
    
    with db_cursor() as cursor:
        # Verifica se o registro já existe para este user_id
        cursor.execute("SELECT 1 FROM google_oauth_tokens WHERE user_id = %s LIMIT 1;", (user_id,))
        existe = cursor.fetchone()
        
        if existe:
            cursor.execute(
                """
                UPDATE google_oauth_tokens 
                SET access_token = %s, refresh_token = %s, token_type = %s, expires_at = %s 
                WHERE user_id = %s;
                """,
                (creds.token, creds.refresh_token, creds.token_type, expires_at, user_id)
            )
            print(f"Token do usuário '{user_id}' ATUALIZADO com sucesso no banco de dados.")
        else:
            cursor.execute(
                """
                INSERT INTO google_oauth_tokens (user_id, access_token, refresh_token, token_type, expires_at)
                VALUES (%s, %s, %s, %s, %s);
                """,
                (creds.token, creds.refresh_token, creds.token_type, expires_at, user_id)
            )
            print(f"Novo token do usuário '{user_id}' INSERIDO com sucesso no banco de dados.")

def main():
    creds = None
    
    # Busca o ID da Conta Master definido no seu arquivo .env
    user_id = os.getenv("GOOGLE_MASTER_USER_ID")
    if not user_id:
        print("AVISO: GOOGLE_MASTER_USER_ID não encontrado no .env. Usando 'master_user_default'.")
        user_id = "master_user_default"
        
    print(f"Iniciando fluxo de autenticação para o ID: {user_id}")

    # Mantém a verificação local por arquivo JSON (caso queira usar para outros scripts de teste)
    if os.path.exists("token.json"):
        try:
            creds = Credentials.from_authorized_user_file("token.json", SCOPES)
            print("Token existente encontrado localmente (token.json).")
        except Exception:
            print("Token local incompatível ou corrompido. Será gerado um novo.")
            creds = None
        
    # Se o token não existir ou estiver inválido
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expirado. Tentando atualizar automaticamente com o Google...")
            try:
                creds.refresh(Request())
                print("Token atualizado com sucesso!")
            except Exception as e:
                print(f"Erro ao atualizar token automaticamente: {e}")
                creds = None
                
        if not creds:
            if not os.path.exists("client_secrets.json"):
                print("ERRO CRÍTICO: O arquivo 'client_secrets.json' não foi encontrado nesta pasta.")
                print("Por favor, baixe o JSON de credenciais OAuth (Desktop App) do Google Cloud Console,")
                print("renomeie-o para 'client_secrets.json' e salve-o aqui.")
                return

            print("Abrindo o navegador para você realizar o login...")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            
            # Executa o servidor local e força o consentimento para obter o Refresh Token permanente
            creds = flow.run_local_server(
                port=0,
                access_type='offline',
                prompt='consent'
            )
            
        # Salva localmente em arquivo
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        print("Arquivo 'token.json' atualizado com sucesso localmente.")

    # Tenta salvar centralizado no banco de dados do sistema
    try:
        salvar_token_no_banco(user_id, creds)
        print("=== AUTENTICAÇÃO CONCLUÍDA EM AMBOS OS FLUXOS (ARQUIVO E BANCO DE DADOS) ===")
    except Exception as err:
        print(f"ERRO CRÍTICO: Não foi possível salvar as credenciais no Banco de Dados: {err}")

if __name__ == "__main__":
    main()