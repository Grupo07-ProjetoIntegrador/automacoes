import argparse
import logging
from datetime import datetime, timedelta
from database import db_cursor
from services import whatsapp_service

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def obter_treinamentos_por_data(data_pesquisa_str: str):
    """
    Busca treinamentos que ocorrem na data especificada (formato YYYY-MM-DD).
    Retorna uma lista de dicionários contendo os dados do treinamento.
    """
    query = """
        SELECT id, tema, local, horario_inicio, horario_fim, data
        FROM treinamentos
        WHERE data::date = %s::date
    """
    try:
        with db_cursor() as cursor:
            cursor.execute(query, (data_pesquisa_str,))
            rows = cursor.fetchall()
            treinamentos = []
            for row in rows:
                # Extrai horários limpos (de timestamp para string formatada de hora)
                h_inicio = row[3].strftime("%H:%M") if isinstance(row[3], datetime) else str(row[3])
                h_fim = row[4].strftime("%H:%M") if isinstance(row[4], datetime) else str(row[4])
                
                treinamentos.append({
                    "id": row[0],
                    "tema": row[1],
                    "local": row[2],
                    "horario_inicio": h_inicio,
                    "horario_fim": h_fim,
                    "data": row[5].strftime("%d/%m/%Y") if hasattr(row[5], 'strftime') else str(row[5])
                })
            return treinamentos
    except Exception as e:
        logger.error(f"Erro ao buscar treinamentos para a data {data_pesquisa_str}: {e}")
        return []

def obter_participantes_pendentes(treinamento_id: str):
    """
    Busca todos os participantes inscritos como 'PENDENTE' em um determinado treinamento.
    """
    query = """
        SELECT nome_participante, telefone, email
        FROM presencas
        WHERE treinamento_id = %s AND status_presenca = 'PENDENTE'
    """
    try:
        with db_cursor() as cursor:
            cursor.execute(query, (treinamento_id,))
            rows = cursor.fetchall()
            return [{"nome": r[0], "telefone": r[1], "email": r[2]} for r in rows]
    except Exception as e:
        logger.error(f"Erro ao buscar participantes pendentes para treinamento {treinamento_id}: {e}")
        return []

def processar_lembretes(data_referencia: datetime):
    """
    Processa os lembretes de WhatsApp para a data_referencia informada.
    Lembrete D-0: Treinamentos ocorrendo na data de referência.
    Lembrete D-1: Treinamentos ocorrendo no dia seguinte à data de referência (amanhã).
    """
    data_hoje_str = data_referencia.strftime("%Y-%m-%d")
    data_amanha_str = (data_referencia + timedelta(days=1)).strftime("%Y-%m-%d")
    
    logger.info(f"Iniciando envio de lembretes. Referência: {data_hoje_str}")

    # ==================== PROCESSAMENTO D-0 (DIA DO EVENTO) ====================
    treinamentos_hoje = obter_treinamentos_por_data(data_hoje_str)
    logger.info(f"Treinamentos encontrados para HOJE ({data_hoje_str}): {len(treinamentos_hoje)}")
    
    for t in treinamentos_hoje:
        participantes = obter_participantes_pendentes(t["id"])
        logger.info(f"Treinamento '{t['tema']}': {len(participantes)} participante(s) pendente(s) hoje.")
        
        for p in participantes:
            if not p["telefone"]:
                continue
                
            mensagem_hoje = (
                f"Olá, {p['nome']}! É hoje! 🚀\n\n"
                f"Lembramos que o treinamento *'{t['tema']}'* iniciará às *{t['horario_inicio']}* no local: *{t['local']}*.\n\n"
                f"Ao chegar ao auditório, faça o check-in lendo o QR Code exibido no telão para confirmar sua presença. Te vemos lá!"
            )
            whatsapp_service.enviar_mensagem_whatsapp(p["telefone"], p["nome"], mensagem_hoje)

    # ==================== PROCESSAMENTO D-1 (VÉSPERA DO EVENTO) ====================
    treinamentos_amanha = obter_treinamentos_por_data(data_amanha_str)
    logger.info(f"Treinamentos encontrados para AMANHÃ ({data_amanha_str}): {len(treinamentos_amanha)}")
    
    for t in treinamentos_amanha:
        participantes = obter_participantes_pendentes(t["id"])
        logger.info(f"Treinamento '{t['tema']}': {len(participantes)} participante(s) pendente(s) para amanhã.")
        
        for p in participantes:
            if not p["telefone"]:
                continue
                
            mensagem_vespera = (
                f"Olá, {p['nome']}! Tudo bem?\n\n"
                f"Passando para lembrar que amanhã ({t['data']}) às *{t['horario_inicio']}* acontecerá o treinamento *'{t['tema']}'* no local: *{t['local']}*.\n\n"
                f"Sua presença é muito importante. Nos vemos lá!"
            )
            whatsapp_service.enviar_mensagem_whatsapp(p["telefone"], p["nome"], mensagem_vespera)

    logger.info("Envio de lembretes concluído com sucesso.")

if __name__ == "__main__":
    # Permite passar uma data específica via linha de comando para testes locais
    parser = argparse.ArgumentParser(description="Envio de lembretes diários via WhatsApp (D-0 e D-1).")
    parser.add_argument(
        "--data", 
        type=str, 
        help="Data de referência simulada no formato YYYY-MM-DD (ex: 2026-05-25)", 
        default=None
    )
    args = parser.parse_args()

    # Define a data atual (ano base 2026 conforme requisito)
    if args.data:
        try:
            data_ref = datetime.strptime(args.data, "%Y-%m-%d")
        except ValueError:
            logger.error("Formato de data inválido! Use YYYY-MM-DD.")
            exit(1)
    else:
        data_ref = datetime.now()
        # Se por algum motivo o relógio do sistema não estiver em 2026, forçamos o ano para 2026, 
        # mantendo o mês e o dia do sistema
        if data_ref.year != 2026:
            try:
                data_ref = data_ref.replace(year=2026)
            except ValueError:
                # Trata ano bissexto caso seja 29 de fevereiro
                data_ref = data_ref + timedelta(days=1)
                data_ref = data_ref.replace(year=2026)
                
    processar_lembretes(data_ref)
