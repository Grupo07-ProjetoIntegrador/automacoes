# Módulo de Automações & Integrações (Python) — Shopping Flamboyant

Microsserviço assíncrono desenvolvido em **Python 3.10+**, **FastAPI** e **Uvicorn**, encarregado da geração automática de formulários no **Google Forms**, captura de matrículas via **Google Apps Script Web App**, envio de convites e confirmações via **Gmail API**, disparo de lembretes no **WhatsApp** e emissão de relatórios em **PDF**.

Repositório oficial: **[Grupo07-ProjetoIntegrador/automacoes](https://github.com/Grupo07-ProjetoIntegrador/automacoes)**

---

## 📑 Sumário

1. [Visão Geral & Responsabilidades](#-visão-geral--responsabilidades)
2. [Estrutura de Arquivos](#-estrutura-de-arquivos)
3. [Guia Passo a Passo: Google Cloud Console](#-guia-passo-a-passo-google-cloud-console)
4. [Código Oficial & Guia: Google Apps Script](#-código-oficial--guia-google-apps-script)
5. [Por que o ngrok é Obrigatório Localmente?](#-por-que-o-ngrok-é-obrigatório-localmente)
6. [Fila Assíncrona de Tarefas (`job_queue`)](#-fila-assíncrona-de-tarefas-job_queue)
7. [Cron de Lembretes do WhatsApp (D-1 e D-0)](#-cron-de-lembretes-do-whatsapp-d-1-e-d-0)
8. [Variáveis de Ambiente (`.env`)](#-variáveis-de-ambiente-env)
9. [Como Rodar Localmente](#-como-rodar-localmente)
10. [Referência de Endpoints da API Python](#-referência-de-endpoints-da-api-python)

---

## 🤖 Visão Geral & Responsabilidades

O microsserviço de automações desonera o backend central de tarefas pesadas de integração externa:
- **Criação de Google Forms Dinâmicos**: Monta perguntas padronizadas, injeta dinamicamente as lojas ativas do shopping vindas do banco de dados e restringe respostas a 1 por participante.
- **Integração com Google Apps Script**: Cadastra gatilhos `onFormSubmit` programaticamente em cada formulário criado para envio imediato de webhooks.
- **Envio de Notificações com a Conta do Usuário**: Utiliza a Gmail API com renovação automática de tokens (OAuth Auto-Refresh) para disparar e-mails institucionais do organizador.
- **Worker Multithread com Fila de Tarefas**: Processa tarefas em segundo plano sem travar requisições HTTP do frontend.
- **Lembretes Automatizados**: Script disparado por agendador para notificar participantes na véspera e no dia do evento via WhatsApp.
- **Relatórios Gráficos em PDF**: Geração em tempo de execução de Dossiês de Lojas e Atas de Presença através da biblioteca ReportLab.

---

## 📂 Estrutura de Arquivos

```text
automacoes/
├── services/
│   ├── email_service.py            # Despacho via Gmail API (tokens OAuth do banco) e fallback SMTP
│   ├── gerar_pdf.py                # Geração de PDFs de dossiê e lista de chamada com ReportLab
│   └── whatsapp_service.py         # Envio de mensagens via Evolution API ou gravação em log mock
├── templates/
│   └── checkin.html                # Template HTML legado de check-in móvel
├── auth_google.py                  # Script interativo de autenticação inicial no Google (gera token.json)
├── config.py                       # Carregamento e validação de variáveis de ambiente
├── cron_lembretes.py               # Rotina de lembretes D-1 e D-0 para inscritos pendentes
├── database.py                     # Gerenciamento de conexões e cursores com o PostgreSQL (Supabase)
├── forms_handler.py                # Criação, deleção e vinculação de gatilhos do Google Forms
├── main.py                         # Aplicação FastAPI, rotas de webhooks e inicialização do worker
├── worker.py                       # Thread em background que consome a tabela 'job_queue' do Postgres
├── client_secrets.example.json     # Modelo do arquivo OAuth Client Desktop do Google Cloud
├── credentials.example.json        # Modelo do arquivo de Service Account do Google Cloud
├── token.example.json              # Modelo do token OAuth gerado pelo auth_google.py
├── .env.example                    # Modelo oficial de variáveis de ambiente
├── requirements.txt                # Dependências Python (FastAPI, google-api-python-client, etc.)
└── Dockerfile                      # Imagem Docker para execução em container
```

---

## ☁️ Guia Passo a Passo: Google Cloud Console

Para que as automações funcionem com o Google Forms e Gmail, siga as instruções abaixo:

### 1. Criar o Projeto no GCP
1. Acesse o **[Google Cloud Console](https://console.cloud.google.com)**.
2. Crie um projeto (ex: `flamboyant-automacoes`).

### 2. Ativar as APIs Necessárias
Acesse **APIs e Serviços > Biblioteca** e ative cada uma das seguintes APIs:
- **Google Forms API**
- **Google Drive API**
- **Gmail API**
- **Google Sheets API**

### 3. Configurar a Tela de Consentimento (OAuth Consent Screen)
1. Vá em **APIs e Serviços > Tela de permissão OAuth**.
2. Escolha **Externo** e clique em **Criar**.
3. Preencha o nome do app (`Flamboyant Automações`) e seu e-mail de contato.
4. Em **Escopos**, adicione:
   - `https://www.googleapis.com/auth/forms.body`
   - `https://www.googleapis.com/auth/drive`
   - `https://www.googleapis.com/auth/gmail.send`
5. Em **Usuários de Teste (Test Users)**, adicione a sua conta Google que será usada como organizadora.

### 4. Gerar o arquivo `client_secrets.json`
1. Vá em **APIs e Serviços > Credenciais > Criar Credenciais > ID do cliente OAuth**.
2. Selecione o tipo **Aplicativo para Computador (Desktop App)**.
3. Clique em **Criar**, baixe o arquivo JSON gerado e renomeie-o para:
   ```text
   automacoes/client_secrets.json
   ```

### 5. Gerar o arquivo `credentials.json` (Service Account)
1. Em **Credenciais**, clique em **Criar Credenciais > Conta de Serviço (Service Account)**.
2. Dê o nome `robo-flamboyant` e conceda o papel de **Editor**.
3. Clique na conta de serviço criada, vá na aba **Chaves > Adicionar chave > Criar nova chave (JSON)**.
4. Salve o arquivo baixado como:
   ```text
   automacoes/credentials.json
   ```

---

## 📜 Código Oficial & Guia: Google Apps Script

O **Google Apps Script** é o componente que escuta os envios de respostas no Google Forms e faz uma requisição HTTP POST imediata para a nossa API Python.

### Código Oficial do Apps Script (`Código.gs`)
Copie integralmente o código abaixo e cole no seu projeto em **[script.google.com](https://script.google.com)**:

```javascript
// ==============================================================================
// GOOGLE APPS SCRIPT: VINCULAÇÃO E WEBHOOK DE INSCRIÇÃO - SHOPPING FLAMBOYANT
// ==============================================================================

// 1. Recebe a chamada do Python para vincular o Form e criar o gatilho onSubmit
function doPost(e) {
  var lock = LockService.getScriptLock();
  lock.tryLock(10000); // Evita condições de corrida se múltiplos formulários forem criados juntos
  
  try {
    var data = JSON.parse(e.postData.contents);
    var formId = data.form_id;
    var webhookUrl = data.webhook_url;
    var treinamentoId = data.treinamento_id;
    var token = data.token || "";

    // Validação básica de segurança dos dados recebidos
    if (!formId) {
      return ContentService.createTextOutput(JSON.stringify({ status: "error", error: "form_id não fornecido." }))
                           .setMimeType(ContentService.MimeType.JSON);
    }

    // Salva o ID do treinamento atrelado ao formulário específico
    if (treinamentoId) {
      PropertiesService.getScriptProperties().setProperty("treinamento_id_" + formId, treinamentoId);
    }
    
    // Salva a URL pública do Webhook atrelada a este formulário específico
    if (webhookUrl) {
      PropertiesService.getScriptProperties().setProperty("webhook_url_" + formId, webhookUrl);
    }
    
    // Salva o token do webhook atrelado a este formulário específico
    if (token) {
      PropertiesService.getScriptProperties().setProperty("webhook_token_" + formId, token);
    }

    // Limpa gatilhos antigos de forma segura
    var triggers = ScriptApp.getProjectTriggers();
    for (var i = 0; i < triggers.length; i++) {
      try {
        if (triggers[i].getTriggerSourceId() === formId) {
          ScriptApp.deleteTrigger(triggers[i]);
        }
      } catch (errTrigger) {
        // Ignora caso o acionador não possua ID de origem
      }
    }
    
    // Abre o formulário pelo ID (requer que a conta do script seja editora do form)
    var form = FormApp.openById(formId);
    
    // Cria o gatilho de envio apontando para a função onFormSubmit
    ScriptApp.newTrigger("onFormSubmit")
             .forForm(form)
             .onFormSubmit()
             .create();

    return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "Gatilho registrado com sucesso para o form " + formId }))
                         .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", error: err.toString() }))
                         .setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

// 2. Disparado automaticamente pelo Google Forms sempre que houver uma resposta
function onFormSubmit(e) {
  try {
    if (!e || !e.source) {
      Logger.log("Erro: Evento ou origem do formulário não detectados.");
      return;
    }

    var form = e.source;
    var formId = form.getId();
    
    var formResponse = e.response;
    if (!formResponse) {
      Logger.log("Erro: Objeto de resposta não encontrado no evento.");
      return;
    }

    var answers = {};
    var itemResponses = formResponse.getItemResponses();
    itemResponses.forEach(function(item) {
      answers[item.getItem().getTitle()] = item.getResponse();
    });

    var treinamentoId = PropertiesService.getScriptProperties().getProperty("treinamento_id_" + formId);
    var webhookUrl = PropertiesService.getScriptProperties().getProperty("webhook_url_" + formId);
    var webhookToken = PropertiesService.getScriptProperties().getProperty("webhook_token_" + formId);

    if (!webhookUrl) {
      Logger.log("Erro: URL do webhook não configurada para o form " + formId);
      return;
    }

    var payload = {
      treinamento_id: treinamentoId || "",
      form_id: formId,
      respondente_email: formResponse.getRespondentEmail() || "",
      enviado_em: formResponse.getTimestamp(),
      nome_representante: answers["Nome do Representante"] || "",
      email: answers["E-mail"] || "",
      telefone: answers["Telefone"] || "",
      cargo: answers["Cargo"] || "",
      nome_loja: answers["Nome da Loja"] || ""
    };

    var options = {
      method: "post",
      contentType: "application/json",
      payload: JSON.stringify(payload),
      headers: webhookToken ? { "X-Automacoes-Token": webhookToken } : {},
      muteHttpExceptions: true
    };

    var response = UrlFetchApp.fetch(webhookUrl, options);
    Logger.log("Resposta do Webhook (" + response.getResponseCode() + "): " + response.getContentText());

  } catch (err) {
    Logger.log("Erro crítico na execução do onFormSubmit: " + err.toString());
  }
}

function testeManualInternet() {
  var resposta = UrlFetchApp.fetch("https://httpbin.org/get");
  Logger.log("Internet autorizada com sucesso! Resposta: " + resposta.getResponseCode());
}

function criarGatilhoManualVersaoAtual() {
  var idDoForm = "1sbBt58nDA2zMO-gdbMTjJ4fP07juALYh2Kd7oQCu-mc"; 
  var form = FormApp.openById(idDoForm);
  ScriptApp.newTrigger("onFormSubmit")
           .forForm(form)
           .onFormSubmit()
           .create();
  Logger.log("Gatilho recriado manualmente na versão atual!");
}
```

### Como Publicar como Web App
1. No Apps Script, clique em **Implantar > Nova implantação**.
2. Selecione o tipo **Aplicativo da Web (Web App)**:
   - **Executar como**: **Eu** (`seu-email@gmail.com`).
   - **Quem tem acesso**: **Qualquer pessoa** (*Anyone*).
3. Copie a URL gerada (terminada em `/exec`) e salve no `.env`:
   ```env
   APPS_SCRIPT_WEBAPP_URL=https://script.google.com/macros/s/SEU_DEPLOYMENT_ID/exec
   APPS_SCRIPT_TOKEN=seu_token_secreto_aqui
   ```

---

## 🌐 Por que o ngrok é Obrigatório Localmente?

Quando um lojista envia uma resposta no Google Forms:
1. O Google Forms executa o gatilho `onFormSubmit` nos data centers do Google.
2. O Apps Script dispara um `UrlFetchApp.fetch(webhookUrl, ...)`.
3. Se a sua `webhookUrl` for `http://localhost:8000`, **o servidor do Google tentará acessar a si mesmo e falhará**, pois `localhost` não é roteável na internet pública.
4. O **[ngrok](https://ngrok.com)** cria um túnel HTTPS seguro apontando para sua máquina local:
   ```powershell
   ngrok http 8000
   ```
5. Você define `AUTOMACOES_PUBLIC_URL=https://seu-subdominio.ngrok-free.app` no seu `.env`. Dessa forma, o Google Apps Script entrega o webhook com sucesso no seu computador.

> Em ambiente de **produção** (com Caddy/Docker ou servidor em nuvem), o ngrok não é necessário porque o servidor já possui um domínio público com HTTPS (ex: `https://jpmallflamboyant.live`).

---

## ⚙️ Fila Assíncrona de Tarefas (`job_queue`)

Para garantir que a resposta HTTP do cadastro de treinamentos seja instantânea (< 200ms), a geração do Google Forms e o envio massivo de e-mails podem ser enfileirados na tabela `job_queue`:

1. O backend em Go insere um registro na tabela `job_queue` com status `'pending'`.
2. O arquivo `worker.py` roda em uma thread em background (`daemon=True`) dentro do processo do FastAPI.
3. O worker executa um polling com trava segura a cada 5 segundos:
   ```sql
   SELECT id, task_type, payload 
   FROM job_queue 
   WHERE status = 'pending' 
   ORDER BY created_at ASC 
   LIMIT 1 
   FOR UPDATE SKIP LOCKED;
   ```
4. Ao processar, o worker atualiza o status para `'completed'` ou registra o erro em `error_message` com status `'failed'`.

---

## ⏰ Cron de Lembretes do WhatsApp (D-1 e D-0)

O script `cron_lembretes.py` é responsável por avisar os colaboradores inscritos:
- **Lembrete D-1 (Véspera)**: Busca treinamentos com data amanhã e envia mensagem reforçando horário, tema e local.
- **Lembrete D-0 (Dia do Evento)**: Busca treinamentos de hoje e envia mensagem matinal lembrando de realizar o check-in lendo o QR Code no auditório.

### Execução Manual do Cron:
```powershell
# Executa para a data atual do sistema:
python cron_lembretes.py

# Simula a execução para uma data específica:
python cron_lembretes.py --data 2026-09-15
```

### Modo Mock vs Produção
No arquivo `.env`:
- `WHATSAPP_API_MODE=mock`: Não dispara mensagens reais; grava todas as mensagens simuladas em `logs/whatsapp_envios.log`.
- `WHATSAPP_API_MODE=production`: Faz requisições HTTP POST para a instância configurada da Evolution API.

---

## ⚙️ Variáveis de Ambiente (`.env`)

Crie o arquivo `automacoes/.env` baseado em [automacoes/.env.example](.env.example):

```env
# Banco de dados PostgreSQL (Supabase)
DATABASE_URL=postgresql://postgres:sua_senha@db.sua_referencia.supabase.co:5432/postgres

# Backend Core em Go
BACKEND_URL=http://localhost:8080

# URL pública do ngrok ou domínio de produção
AUTOMACOES_PUBLIC_URL=https://seu-subdominio.ngrok-free.dev

# Google Apps Script
APPS_SCRIPT_WEBAPP_URL=https://script.google.com/macros/s/SEU_DEPLOYMENT_ID/exec
APPS_SCRIPT_TOKEN=seu_token_compartilhado_aqui

# Identificador da conta Master e arquivos Google
GOOGLE_MASTER_USER_ID=master_user_default
GOOGLE_SERVICE_ACCOUNT_FILE=credentials.json
GOOGLE_CLIENT_ID=seu-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=seu_client_secret

# Configurações de SMTP (Fallback)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_EMAIL=seu_email@gmail.com
SMTP_PASSWORD=sua_senha_de_aplicativo
DEFAULT_DESTINATION_EMAIL=seu_email_destino@gmail.com

# WhatsApp
WHATSAPP_API_MODE=mock
WHATSAPP_API_URL=https://api.evolution.sua-instancia.com/message/sendText
WHATSAPP_API_TOKEN=seu_token_aqui
```

---

## 🚀 Como Rodar Localmente

### 1. Criar e Ativar o Ambiente Virtual
```powershell
cd automacoes
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell
# source .venv/bin/activate    # Linux / macOS
```

### 2. Instalar Dependências
```powershell
pip install -r requirements.txt
```

### 3. Autenticação Inicial com o Google (Gerar `token.json`)
Certifique-se de que o arquivo `client_secrets.json` está na pasta `automacoes/` e execute:
```powershell
python auth_google.py
```
O script abrirá uma janela do navegador para login e consentimento da conta Google Master. Ao concluir, gerará o `token.json` e persistirá as credenciais na tabela `google_oauth_tokens` do Supabase.

### 4. Iniciar o Servidor FastAPI com Uvicorn
```powershell
uvicorn main:app --reload --port 8000
```
O serviço iniciará na porta **`http://localhost:8000`** e a thread do worker da fila de tarefas começará a rodar automaticamente.

### 5. Iniciar o ngrok para Webhooks
Em outro terminal:
```powershell
ngrok http 8000
```
Copie o endereço HTTPS fornecido pelo ngrok e configure a variável `AUTOMACOES_PUBLIC_URL` no `.env`.

---

## 📚 Referência de Endpoints da API Python

| Método | Endpoint | Descrição |
| :--- | :--- | :--- |
| `GET` | `/health` | Diagnóstico de conexão com o banco e status do ambiente. |
| `POST` | `/api/automacoes/gerar-forms` | Recebe solicitação do Go e gera o Google Forms em background. |
| `POST` | `/api/automacoes/disparar-convite` | Dispara e-mails de convite para a lista segmentada de lojistas. |
| `POST` | `/api/automacoes/notificar-presenca-validada` | Envia e-mail de confirmação de presença após o check-in. |
| `POST` | `/api/automacoes/notificar-inscricao-confirmada` | Envia e-mail confirmando a matrícula do colaborador. |
| `POST` | `/api/automacoes/webhook-inscricao` | Recebe as respostas enviadas pelo Google Apps Script e repassa ao Go. |
| `POST` | `/api/automacoes/apagar-form` | Remove o vínculo do formulário e tenta apagá-lo no Google Drive. |
| `POST` | `/api/automacoes/pdf/dossie` | Gera e devolve em streaming o PDF do dossiê histórico da loja. |
| `POST` | `/api/automacoes/pdf/chamada` | Gera e devolve em streaming o PDF da ata de chamada do evento. |