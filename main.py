import os
import logging
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

import config
from database import db_cursor, test_connection
from forms_handler import criar_google_form, apagar_formulario
from services.email_service import enviar_email_formulario

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Módulo de Automações - Shopping Flamboyant",
    description="Serviços integrados de Google Forms, E-mail, WhatsApp e Geolocalização.",
    version="1.0.0"
)

# Configura CORS para permitir chamadas do navegador (caso a API do Python seja consumida pelo front)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== SCHEMAS PYDANTIC ====================

class GerarFormsRequest(BaseModel):
    treinamento_id: str
    tema: str
    email_destino: str = None  # Opcional, se fornecido o link é enviado para ele
    user_id: str = None  # Optional Supabase user id to create the form in the user's account

class WebhookInscricaoRequest(BaseModel):
    treinamento_id: str
    nome_representante: str
    email: EmailStr
    telefone: str
    cargo: str
    nome_loja: str
    luc: str = ""

class ApagarFormsRequest(BaseModel):
    treinamento_id: str
    user_id: str = None

# ==================== ROTAS DA API ====================

@app.get("/health")
def health_check():
    """Rota para verificar a saúde do serviço e a conexão com o Supabase."""
    db_ok = test_connection()
    return {
        "status": "online" if db_ok else "degraded",
        "database_connected": db_ok,
        "environment": "production" if os.path.exists(config.GOOGLE_SERVICE_ACCOUNT_FILE) else "simulation"
    }

@app.get("/checkin", response_class=HTMLResponse)
def checkin_page(treinamento_id: str = Query(..., description="ID do treinamento correspondente")):
    """Retorna a interface do checkin.html para o celular do lojista."""
    template_path = Path(__file__).parent / "templates" / "checkin.html"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template de check-in não encontrado.")
    
    with open(template_path, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    return html_content

def background_gerar_e_enviar(req: GerarFormsRequest):
    """Tarefa em background para gerar o Forms e disparar e-mail sem travar a requisição HTTP."""
    try:
        # 1. Cria o forms (tenta usar credenciais do user se fornecido)
        link_forms = criar_google_form(req.treinamento_id, req.tema, req.user_id)
        
        # 2. Dispara e-mail
        dest = req.email_destino or config.DEFAULT_DESTINATION_EMAIL
        email_enviado = enviar_email_formulario(req.tema, link_forms, dest, req.user_id)

        if email_enviado:
            logger.info(f"Processo de geração e envio de e-mail concluído para Treinamento ID {req.treinamento_id}")
        else:
            logger.warning(
                f"Formulário criado, mas o e-mail nao foi enviado para Treinamento ID {req.treinamento_id}. "
                "Verifique se a conta Google conectada foi reautorizada com o escopo gmail.send."
            )
    except Exception as e:
        logger.error(f"Erro na tarefa em background de geração de forms: {e}")

@app.post("/api/automacoes/gerar-forms")
def endpoint_gerar_forms(req: GerarFormsRequest, background_tasks: BackgroundTasks):
    """
    Acionado pelo backend em Go quando um novo treinamento é cadastrado.
    Inicia em background a geração do Forms e o envio do e-mail.
    """
    # Valida se o treinamento existe no banco de dados antes
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Treinamento informado não existe no banco de dados.")

    # Agenda a tarefa para rodar assincronamente e responde imediatamente ao Go
    background_tasks.add_task(background_gerar_e_enviar, req)
    
    return {
        "status": "processing",
        "message": f"A geração do Google Forms para o treinamento '{req.tema}' foi iniciada em segundo plano."
    }

@app.post("/api/automacoes/apagar-form")
def endpoint_apagar_form(req: ApagarFormsRequest):
    """Remove o vinculo do formulario e tenta apagar o arquivo no Google Drive."""
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Treinamento informado não existe no banco de dados.")

    result = apagar_formulario(req.treinamento_id, req.user_id)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail="Formulario ainda não foi gerado.")

    return {
        "status": "deleted",
        "form_id": result.get("form_id", ""),
        "drive_deleted": result.get("drive_deleted", False)
    }

@app.post("/api/automacoes/webhook-inscricao")
def endpoint_webhook_inscricao(req: WebhookInscricaoRequest, request: Request):
    """
    Recebe as respostas do Google Forms via Apps Script.
    Valida se o treinamento existe e repassa em formato estruturado para o backend Go persistir.
    """
    # 0. Valida token opcional
    if config.APPS_SCRIPT_TOKEN:
        token = request.headers.get("X-Automacoes-Token", "")
        if token != config.APPS_SCRIPT_TOKEN:
            raise HTTPException(status_code=401, detail="Token do webhook invalido.")

    # 1. Valida se o treinamento existe
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"O treinamento ID '{req.treinamento_id}' não existe no banco de dados.")

    # 2. Repassa os dados para o backend em Go processar a criação silenciosa de lojas e a matrícula
    url_go = f"{config.BACKEND_URL}/api/treinamentos/webhook-forms"
    
    payload = {
        "treinamento_id": req.treinamento_id,
        "luc": req.luc or "",
        "nome_loja": req.nome_loja,
        "nome_representante": req.nome_representante,
        "email": req.email,
        "telefone": req.telefone,
        "cargo": req.cargo
    }

    try:
        response = requests.post(url_go, json=payload, timeout=10)
        
        if response.status_code in [200, 201]:
            logger.info(f"Matrícula processada via webhook para participante: {req.nome_representante}")
            return {
                "status": "success",
                "message": "Inscrição processada com sucesso no backend Go.",
                "detail": response.text
            }
        else:
            logger.error(f"Erro no repasse da inscrição para o Go. Status: {response.status_code} - Resposta: {response.text}")
            raise HTTPException(
                status_code=502, 
                detail=f"Erro no backend de persistência em Go: {response.text}"
            )
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Não foi possível conectar ao backend Go no endereço {url_go}: {e}")
        raise HTTPException(
            status_code=503, 
            detail="O serviço de persistência em Go está temporariamente indisponível. Tente novamente mais tarde."
        )
