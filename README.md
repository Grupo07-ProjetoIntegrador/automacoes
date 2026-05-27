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
	- Ajuste as variaveis em `config.py` conforme seu ambiente.
	- Garanta que os arquivos `client_secrets.json`, `credentials.json` e `token.json` estejam corretos.

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