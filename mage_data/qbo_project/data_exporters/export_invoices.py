from mage_ai.data_preparation.shared.secrets import get_secret_value
from sqlalchemy import create_engine, text
import pandas as pd

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter


@data_exporter
def export_data_to_postgres(df: pd.DataFrame, **kwargs):
    """
    Exporta datos a Postgres esquema 'raw' con lógica de Upsert (Idempotencia).
    """
    # 1. Recuperar credenciales seguras
    user = get_secret_value('POSTGRES_USER')
    password = get_secret_value('POSTGRES_PASSWORD')
    host = get_secret_value('POSTGRES_HOST')
    db = get_secret_value('POSTGRES_DB')
    
    # 2. Crear conexión (SQLAlchemy)
    conn_str = f'postgresql://{user}:{password}@{host}:5432/{db}'
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        trans = connection.begin()
        try:
            # 3. Asegurar que existe el esquema RAW
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
            
            # 4. Crear tabla si no existe (con JSONB para el payload)
            # Definimos 'id' como PRIMARY KEY para poder detectar duplicados
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS raw.qb_invoices (
                id VARCHAR(50) PRIMARY KEY,
                payload JSONB,
                ingested_at_utc TIMESTAMP,
                extract_window_start_utc VARCHAR(50),
                extract_window_end_utc VARCHAR(50),
                page_number INTEGER
            );
            """
            connection.execute(text(create_table_sql))
            
            # 5. Ejecutar UPSERT (Insert on Conflict Update)
            # Esto cumple el requisito de idempotencia: si el ID ya existe, actualiza los datos.
            upsert_sql = text("""
            INSERT INTO raw.qb_invoices (id, payload, ingested_at_utc, extract_window_start_utc, extract_window_end_utc, page_number)
            VALUES (:id, :payload, :ingested_at_utc, :extract_window_start_utc, :extract_window_end_utc, :page_number)
            ON CONFLICT (id) DO UPDATE SET
                payload = EXCLUDED.payload,
                ingested_at_utc = EXCLUDED.ingested_at_utc,
                extract_window_start_utc = EXCLUDED.extract_window_start_utc,
                extract_window_end_utc = EXCLUDED.extract_window_end_utc,
                page_number = EXCLUDED.page_number;
            """)
            
            # Convertimos el DF a diccionario para pasarlo a SQLAlchemy
            data_to_insert = df.to_dict(orient='records')
            
            # Ejecución masiva
            connection.execute(upsert_sql, data_to_insert)
            
            trans.commit()
            print(f"Éxito: {len(df)} registros procesados (Upsert) en raw.qb_invoices")
            
        except Exception as e:
            trans.rollback()
            raise e