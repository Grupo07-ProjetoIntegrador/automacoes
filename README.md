# automacoes

## Visao geral
Esta pasta contem scripts de automacoes para envio de lembretes, integracoes com Google e servicos de email/WhatsApp.

## Requisitos
- Python 3.10+
- Windows, macOS ou Linux

## Como baixar
1. Clone o repositorio:
	```bash
	git clone <URL_DO_REPOSITORIO>
	```
2. Entre na pasta das automacoes:
	```bash
	cd automacoes
	```

## Como configurar
1. Crie um ambiente virtual:
	```bash
	python -m venv .venv
	```
2. Ative o ambiente virtual:
	- Windows (PowerShell):
	  ```bash
	  .\.venv\Scripts\Activate.ps1
	  ```
	- macOS/Linux:
	  ```bash
	  source .venv/bin/activate
	  ```
3. Instale as dependencias:
	```bash
	pip install -r requirements.txt
	```
4. Configure os arquivos locais:
	- Copie `.env.example` para `.env` e preencha os valores.
	- Ajuste as variaveis em `config.py` conforme seu ambiente.
	- Garanta que os arquivos `client_secrets.json`, `credentials.json` e `token.json` estejam corretos.
	- Use os exemplos em `client_secrets.example.json`, `credentials.example.json` e `token.example.json`.

## Como obter credenciais
### Google Cloud Service Account (`credentials.json`)
1. Acesse o Google Cloud Console e selecione o projeto.
2. Ative as APIs usadas (ex: Google Sheets, Gmail, Calendar).
3. Va em IAM e Admin > Service Accounts e crie uma conta.
4. Gere uma chave JSON e salve como `credentials.json` na pasta `automacoes/`.

Links uteis:
- https://console.cloud.google.com/
- https://console.cloud.google.com/apis/library
- https://console.cloud.google.com/iam-admin/serviceaccounts

Checklist de APIs comuns:
- Google Sheets API
- Gmail API
- Google Calendar API

### OAuth Client (`client_secrets.json`)
1. No Google Cloud Console, va em APIs e services > Credentials.
2. Crie um OAuth Client ID do tipo Desktop App.
3. Baixe o JSON e renomeie para `client_secrets.json`.

Link direto:
- https://console.cloud.google.com/apis/credentials

### Token OAuth (`token.json`)
1. Execute o fluxo de autorizacao do Google (geralmente pelo script de auth).
2. O arquivo `token.json` sera gerado automaticamente.
3. Copie para a pasta `automacoes/` se necessario.

## Como rodar
Execute o script principal:
```bash
python main.py
```

Ou rode a API com Uvicorn:
```bash
uvicorn main:app --reload --port 8000
```

## Agendamento (opcional)
Para tarefas recorrentes, use o script de cron:
```bash
python cron_lembretes.py
```

## Observacoes
- Logs sao gravados em `logs/`.
- Os servicos de email e WhatsApp ficam em `services/`.