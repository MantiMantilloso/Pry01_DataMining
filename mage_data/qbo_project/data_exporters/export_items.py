from mage_ai.data_preparation.shared.secrets import get_secret_value
from sqlalchemy import create_engine, text
import pandas as pd

if 'data_exporter' not in globals():
    from mage_ai.data_preparation.decorators import data_exporter

@data_exporter
def export_data_to_postgres(df: pd.DataFrame, **kwargs):
    user = get_secret_value('POSTGRES_USER')
    password = get_secret_value('POSTGRES_PASSWORD')
    host = get_secret_value('POSTGRES_HOST')
    db = get_secret_value('POSTGRES_DB')
    
    conn_str = f'postgresql://{user}:{password}@{host}:5432/{db}'
    engine = create_engine(conn_str)

    with engine.connect() as connection:
        trans = connection.begin()
        try:
            connection.execute(text("CREATE SCHEMA IF NOT EXISTS raw;"))
            
            # --- CAMBIO CLAVE: Nombre de tabla qb_items ---
            create_table_sql = """
            CREATE TABLE IF NOT EXISTS raw.qb_items (
                id VARCHAR(50) PRIMARY KEY,
                payload JSONB,
                ingested_at_utc TIMESTAMP,
                extract_window_start_utc VARCHAR(50),
                extract_window_end_utc VARCHAR(50),
                page_number INTEGER
            );
            """
            connection.execute(text(create_table_sql))
            
            upsert_sql = text("""
            INSERT INTO raw.qb_items (id, payload, ingested_at_utc, extract_window_start_utc, extract_window_end_utc, page_number)
            VALUES (:id, :payload, :ingested_at_utc, :extract_window_start_utc, :extract_window_end_utc, :page_number)
            ON CONFLICT (id) DO UPDATE SET
                payload = EXCLUDED.payload,
                ingested_at_utc = EXCLUDED.ingested_at_utc,
                extract_window_start_utc = EXCLUDED.extract_window_start_utc,
                extract_window_end_utc = EXCLUDED.extract_window_end_utc,
                page_number = EXCLUDED.page_number;
            """)
            
            data_to_insert = df.to_dict(orient='records')
            connection.execute(upsert_sql, data_to_insert)
            
            trans.commit()
            print(f"Éxito: {len(df)} items procesados en raw.qb_items")
            
        except Exception as e:
            trans.rollback()
            raise e