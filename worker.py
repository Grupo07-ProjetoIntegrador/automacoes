import time
import json
import logging
from database import get_connection
from main import background_gerar_e_enviar, background_disparar_convites, GerarFormsRequest, DisparoConviteRequest

logger = logging.getLogger("worker")
logger.setLevel(logging.INFO)

def processar_job(job_id, task_type, payload):
    logger.info(f"Processando job {job_id} do tipo {task_type}")
    
    if task_type == 'gerar_forms':
        # Instancia o request do Pydantic
        req = GerarFormsRequest(**payload)
        # Executa síncronamente na thread do worker
        background_gerar_e_enviar(req)
        
    elif task_type == 'disparar_convites':
        req = DisparoConviteRequest(**payload)
        background_disparar_convites(req)
        
    else:
        raise ValueError(f"Tipo de tarefa desconhecido: {task_type}")

def iniciar_worker():
    logger.info("Worker da fila de tarefas iniciado...")
    while True:
        conn = None
        try:
            conn = get_connection()
            with conn.cursor() as cur:
                # Busca o próximo job pendente e trava a linha
                cur.execute("""
                    SELECT id, task_type, payload 
                    FROM job_queue 
                    WHERE status = 'pending' 
                    ORDER BY created_at ASC 
                    LIMIT 1 
                    FOR UPDATE SKIP LOCKED;
                """)
                job = cur.fetchone()
                
                if job:
                    job_id, task_type, payload_raw = job
                    # Se for string (JSON do Go/Postgres), faz parse
                    if isinstance(payload_raw, str):
                        payload = json.loads(payload_raw)
                    else:
                        payload = payload_raw
                    
                    # Marca como em processamento
                    cur.execute("""
                        UPDATE job_queue 
                        SET status = 'processing', updated_at = NOW() 
                        WHERE id = %s;
                    """, (job_id,))
                    conn.commit()
                    
                    try:
                        processar_job(job_id, task_type, payload)
                        with conn.cursor() as update_cur:
                            update_cur.execute("""
                                UPDATE job_queue 
                                SET status = 'completed', updated_at = NOW() 
                                WHERE id = %s;
                            """, (job_id,))
                        conn.commit()
                        logger.info(f"Job {job_id} concluído com sucesso.")
                    except Exception as ex:
                        conn.rollback()
                        with conn.cursor() as error_cur:
                            error_cur.execute("""
                                UPDATE job_queue 
                                SET status = 'failed', error_message = %s, updated_at = NOW() 
                                WHERE id = %s;
                            """, (str(ex), job_id))
                        conn.commit()
                        logger.error(f"Job {job_id} falhou: {ex}")
                
            conn.close()
        except Exception as e:
            logger.error(f"Erro no loop do worker: {e}")
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
            
        time.sleep(5) # Intervalo de 5 segundos para polling

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    iniciar_worker()
