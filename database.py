import psycopg2
from contextlib import contextmanager
import config

def get_connection():
    """Retorna uma conexão bruta com o banco de dados Supabase via URL Postgres."""
    if not config.DATABASE_URL:
        raise ValueError("A variável de ambiente DATABASE_URL não foi definida no arquivo .env!")
    return psycopg2.connect(config.DATABASE_URL)

@contextmanager
def db_cursor():
    """Context manager para gerenciar a abertura/fechamento do cursor e transações (commit/rollback)."""
    conn = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            cursor.close()
            conn.close()

def test_connection():
    """Função simples para testar a conexão com o banco de dados."""
    try:
        with db_cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            if result and result[0] == 1:
                return True
    except Exception as e:
        print(f"Erro ao testar a conexão com o Supabase: {e}")
        return False
    return False
