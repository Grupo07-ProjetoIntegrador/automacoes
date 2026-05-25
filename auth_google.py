import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# Scopes necessários para gerenciar arquivos no Drive (criar formulários) e editar o corpo do Forms
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/forms.body"
]

def main():
    creds = None
    # O arquivo token.json armazena os tokens de acesso e atualização do usuário
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
        print("Token existente encontrado.")
        
    # Se não houver credenciais válidas disponíveis, solicita o login do usuário.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("Token expirado. Tentando atualizar...")
            try:
                creds.refresh(Request())
                print("Token atualizado com sucesso!")
            except Exception as e:
                print(f"Erro ao atualizar token: {e}")
                creds = None
                
        if not creds:
            if not os.path.exists("client_secrets.json"):
                print("ERRO: O arquivo 'client_secrets.json' não foi encontrado na pasta 'automacoes'.")
                print("Por favor, baixe as credenciais OAuth 2.0 (Desktop App) do Google Cloud Console,")
                print("renomeie o arquivo para 'client_secrets.json' e coloque-o nesta pasta.")
                return

            print("Iniciando fluxo de login no navegador...")
            flow = InstalledAppFlow.from_client_secrets_file("client_secrets.json", SCOPES)
            # Executa o servidor local na porta 8085 ou outra disponível para receber o callback
            creds = flow.run_local_server(port=0)
            
        # Salva as credenciais para a próxima execução
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        print("Autenticação realizada com sucesso! O arquivo 'token.json' foi gerado.")

if __name__ == "__main__":
    main()
