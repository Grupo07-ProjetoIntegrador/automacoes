import os
import logging
from pathlib import Path
import requests
from fastapi import FastAPI, HTTPException, Query, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
import io

import config
from database import db_cursor, test_connection
from forms_handler import criar_google_form, apagar_formulario
from services.email_service import enviar_email_formulario, enviar_email_validacao_presenca
from services.gerar_pdf import gerar_pdf_dossie_loja, gerar_pdf_ata_chamada

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
    treinamento: dict
    email_destino: str = None  # Opcional, se fornecido o link é enviado para ele
    user_id: str = None  # Optional Supabase user id to create the form in the user's account


class ConviteDestinatarioRequest(BaseModel):
    nome: str = ""
    email: EmailStr
    segmento: str = ""


class DisparoConviteRequest(BaseModel):
    treinamento_id: str
    treinamento: dict
    modo: str = "individual"
    segmento_loja: str = ""
    segmento_treinamento: str = ""
    destinatarios: list[ConviteDestinatarioRequest] = []
    user_id: str = None


class ValidacaoPresencaRequest(BaseModel):
    treinamento_id: str
    treinamento: dict
    destinatario: ConviteDestinatarioRequest
    user_id: str = None


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


class PDFDossieLojaRequest(BaseModel):
    dados_loja: dict
    period: dict
    historico_treinamentos: list


class PDFAtaChamadaRequest(BaseModel):
    dados_treinamento: dict
    presentes: list
    ausentes: list


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
        link_forms = criar_google_form(req.treinamento_id, req.treinamento, req.user_id)
        
        # 2. Dispara e-mail
        dest = req.email_destino or config.DEFAULT_DESTINATION_EMAIL
        email_enviado = enviar_email_formulario(req.treinamento, link_forms, dest, req.user_id)

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
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Treinamento informado não existe no banco de dados.")

    background_tasks.add_task(background_gerar_e_enviar, req)
    
    return {
        "status": "processing",
        "message": f"A geração do Google Forms para o treinamento '{req.treinamento.get('tema', req.treinamento_id)}' foi iniciada em segundo plano."
    }


def background_disparar_convites(req: DisparoConviteRequest):
    try:
        link_forms = criar_google_form(req.treinamento_id, req.treinamento, req.user_id)

        if req.modo == "segmento_treinamento" and req.segmento_treinamento:
            target = (req.segmento_treinamento or "").strip().lower()
            if target == "geral":
                destinatarios = req.destinatarios
            else:
                destinatarios = [
                    destinatario
                    for destinatario in req.destinatarios
                    if (destinatario.segmento or "").strip().lower() == target
                ]
        elif req.modo == "segmento_loja" and req.segmento_loja:
            seg_loja = (req.segmento_loja or "").strip().lower()
            if seg_loja == "lojas":
                destinatarios = [
                    destinatario
                    for destinatario in req.destinatarios
                    if (destinatario.segmento or "").strip().lower() not in ("alimentação", "academia", "alimentacao")
                ]
            else:
                destinatarios = [
                    destinatario
                    for destinatario in req.destinatarios
                    if (destinatario.segmento or "").strip().lower() == seg_loja
                ]
        else:
            destinatarios = req.destinatarios

        enviados = 0
        for destinatario in destinatarios:
            if enviar_email_formulario(
                req.treinamento,
                link_forms,
                destinatario.email,
                req.user_id,
                nome_destinatario=destinatario.nome,
            ):
                enviados += 1

        logger.info(
            "Disparo de convites concluído para treinamento %s: %s destinatário(s)",
            req.treinamento_id,
            enviados,
        )
    except Exception as e:
        logger.error(f"Erro no disparo de convites em background: {e}")


@app.post("/api/automacoes/disparar-convite")
def endpoint_disparar_convite(req: DisparoConviteRequest, background_tasks: BackgroundTasks):
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Treinamento informado não existe no banco de dados.")

    if not req.destinatarios:
        raise HTTPException(status_code=400, detail="Nenhum destinatário informado para o disparo.")

    background_tasks.add_task(background_disparar_convites, req)

    return {
        "status": "processing",
        "message": "O disparo segmentado de convites foi iniciado em segundo plano.",
        "destinatarios": len(req.destinatarios),
        "modo": req.modo,
    }


def background_notificar_presenca_validada(req: ValidacaoPresencaRequest):
    """Tarefa em segundo plano para buscar credenciais Master da API do Gmail e enviar e-mail."""
    try:
        # 1. Carrega as credenciais da Conta Master antes do disparo utilizando os escopos cheios
        master_id = req.user_id or os.getenv("GOOGLE_MASTER_USER_ID")
        gmail_scopes = [
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/forms",
            "https://www.googleapis.com/auth/forms.body",
            "https://www.googleapis.com/auth/gmail.send"
        ]
        
        try:
            from services.email_service import _obter_credenciais_usuario
            creds_master = _obter_credenciais_usuario(master_id, gmail_scopes)
        except Exception as db_err:
            logger.warning(f"Falha de conexão temporária ao banco Supabase ao obter token master: {db_err}")
            creds_master = None

        # 2. Executa o envio repassando as credenciais injetadas (Evita falhas de concorrência ou fallback SMTP indesejado)
        enviou = enviar_email_validacao_presenca(
            treinamento=req.treinamento,
            email_destinatario=req.destinatario.email,
            nome_destinatario=req.destinatario.nome,
            user_id=master_id,
            usuario_creds=creds_master
        )

        if enviou:
            logger.info(f"E-mail de presença validada enviado com SUCESSO via Gmail API para {req.destinatario.email}")
        else:
            logger.warning(f"Não foi possível processar o envio via Gmail API para {req.destinatario.email}.")
            
    except Exception as e:
        logger.error(f"Erro crítico no fluxo em background de notificação de presença: {e}")


@app.post("/api/automacoes/notificar-presenca-validada")
def notificar_presenca_validada(req: ValidacaoPresencaRequest, background_tasks: BackgroundTasks):
    """
    Acionado após o check-in do lojista. 
    Agenda o envio em background para retornar o HTTP 200 OK imediatamente.
    """
    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Treinamento informado não existe no banco de dados.")

    background_tasks.add_task(background_notificar_presenca_validada, req)

    return {
        "status": "processing",
        "message": f"A notificação de confirmação para '{req.destinatario.email}' foi agendada via Gmail API."
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
    if config.APPS_SCRIPT_TOKEN:
        token = request.headers.get("X-Automacoes-Token", "")
        if token != config.APPS_SCRIPT_TOKEN:
            raise HTTPException(status_code=401, detail="Token do webhook invalido.")

    with db_cursor() as cursor:
        cursor.execute("SELECT id FROM treinamentos WHERE id = %s;", (req.treinamento_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail=f"O treinamento ID '{req.treinamento_id}' não existe no banco de dados.")

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


@app.post("/api/automacoes/pdf/dossie")
def endpoint_pdf_dossie(req: PDFDossieLojaRequest):
    try:
        pdf_bytes = gerar_pdf_dossie_loja(req.dados_loja, req.period, req.historico_treinamentos)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=dossie_{req.dados_loja.get('luc', 'loja')}.pdf"}
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF do Dossie: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao gerar PDF: {str(e)}")


@app.post("/api/automacoes/pdf/chamada")
def endpoint_pdf_chamada(req: PDFAtaChamadaRequest):
    try:
        pdf_bytes = gerar_pdf_ata_chamada(req.dados_treinamento, req.presentes, req.ausentes)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=ata_{req.dados_treinamento.get('id', 'treinamento')}.pdf"}
        )
    except Exception as e:
        logger.error(f"Erro ao gerar PDF da Ata: {e}")
        raise HTTPException(status_code=500, detail=f"Erro interno ao gerar PDF: {str(e)}")