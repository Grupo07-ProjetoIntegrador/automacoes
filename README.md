# Automações Python

Esta pasta contém os serviços em Python usados para gerar Google Forms, receber webhooks, enviar e-mails e integrar com serviços auxiliares.

## O que fica aqui

* Código Python da automação
* Arquivo [automacoes/.env.example](.env.example)
* Arquivos locais [automacoes/.env](.env), [automacoes/client_secrets.json](client_secrets.json), [automacoes/credentials.json](credentials.json) e [automacoes/token.json](token.json)
* Ambiente virtual local `.venv/`, se você optar por usar um isolado dentro desta pasta

## Sobre `.venv`

`.venv` é o ambiente virtual do Python. Ele não é código-fonte e não deve ser versionado. O ideal é criar esse diretório dentro de `automacoes/` quando você for instalar dependências Python nessa subárea.

## Requisitos

* Python 3.10+
* Acesso ao Supabase
* Credenciais Google válidas

## Como configurar

1. Copie [automacoes/.env.example](.env.example) para [automacoes/.env](.env).
2. Preencha as variáveis com os valores do seu ambiente.
3. Crie o ambiente virtual em `automacoes/.venv`.
4. Instale as dependências de [requirements.txt](requirements.txt).
5. Gere ou substitua os arquivos secretos locais do Google.

### Variáveis usadas

* `DATABASE_URL`
* `BACKEND_URL`
* `AUTOMACOES_PUBLIC_URL`
* `APPS_SCRIPT_WEBAPP_URL`
* `APPS_SCRIPT_TOKEN`
* `GOOGLE_SERVICE_ACCOUNT_FILE`
* `GOOGLE_CLIENT_ID`
* `GOOGLE_CLIENT_SECRET`
* `SMTP_SERVER`
* `SMTP_PORT`
* `SMTP_EMAIL`
* `SMTP_PASSWORD`
* `DEFAULT_DESTINATION_EMAIL`
* `WHATSAPP_API_MODE`
* `WHATSAPP_API_URL`
* `WHATSAPP_API_TOKEN`

## Como obter credenciais

### Google Cloud Service Account (`credentials.json`)

1. Acesse o Google Cloud Console.
2. Ative as APIs necessárias para Forms, Drive, Gmail e demais integrações.
3. Crie uma service account.
4. Baixe a chave JSON e salve como [automacoes/credentials.json](credentials.json).

### OAuth Client (`client_secrets.json`)

1. No Google Cloud Console, vá em APIs e serviços > Credenciais.
2. Crie um OAuth Client ID do tipo Desktop App.
3. Baixe o JSON e salve como [automacoes/client_secrets.json](client_secrets.json).

### Token OAuth (`token.json`)

1. Execute o fluxo de autorização do Google.
2. O arquivo [automacoes/token.json](token.json) será gerado.
3. Use o exemplo [automacoes/token.example.json](token.example.json) como modelo.

## Como rodar

```bash
python main.py
```

Ou com Uvicorn:

```bash
uvicorn main:app --reload --port 8000
```

## Webhook automático do Google Forms

Ao criar um Form, o sistema registra o gatilho automaticamente via Apps Script e envia as respostas para:

`{AUTOMACOES_PUBLIC_URL}/api/automacoes/webhook-inscricao`

### Configuração mínima do `.env`

```env
AUTOMACOES_PUBLIC_URL=https://seu-subdominio.ngrok-free.dev
APPS_SCRIPT_WEBAPP_URL=https://script.google.com/macros/s/SEU_DEPLOYMENT_ID/exec
APPS_SCRIPT_TOKEN=seu_token_compartilhado
```

## Expor localmente com ngrok (recomendado para desenvolvimento)

Para testar webhooks e permitir que o Apps Script (ou formulários) enviem dados para sua máquina local, use o `ngrok` para criar um túnel HTTPS público para sua porta local (ex.: 8000).

1. Instale o ngrok em https://ngrok.com/ e autentique usando seu authtoken (apenas uma vez):

```powershell
ngrok authtoken <SEU_NGROK_AUTHTOKEN>
```

2. Abra um túnel para a porta onde o serviço das automações está rodando (ex.: 8000):

```powershell
ngrok http 8000
```

3. O `ngrok` exibirá URLs públicos (ex.: `https://abcd1234.ngrok.app`). Copie a URL HTTPS e atualize `AUTOMACOES_PUBLIC_URL` no seu `.env` com essa URL (sem barra final).

4. Reinicie as automações (se necessário) para que as chamadas usem a nova `AUTOMACOES_PUBLIC_URL`.

Exemplo de `.env` usando ngrok:

```env
AUTOMACOES_PUBLIC_URL=https://abcd1234.ngrok.app
APPS_SCRIPT_WEBAPP_URL=https://script.google.com/macros/s/SEU_DEPLOYMENT_ID/exec
APPS_SCRIPT_TOKEN=seu_token_compartilhado
```

Observações:

- Mantenha o terminal do `ngrok` aberto enquanto estiver testando; se o túnel fechar, a URL pública muda.
- Use a URL HTTPS fornecida pelo `ngrok` — alguns serviços exigem HTTPS para callbacks.
- Se estiver usando o Apps Script Web App para registrar gatilhos, o sistema enviará o `webhook_url` correto ao Apps Script quando criar o Form.


## Boas práticas para GitHub

Não envie para o repositório:

* `.venv/`
* `.env`
* `client_secrets.json`
* `credentials.json`
* `token.json`

Os arquivos `*.example` devem permanecer versionados para orientar novas máquinas.