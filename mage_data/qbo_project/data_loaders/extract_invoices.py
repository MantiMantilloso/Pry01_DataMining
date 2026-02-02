import io
import pandas as pd
import requests
import json
import base64
import time
from mage_ai.data_preparation.shared.secrets import get_secret_value
from datetime import datetime

if 'data_loader' not in globals():
    from mage_ai.data_preparation.decorators import data_loader
if 'test' not in globals():
    from mage_ai.data_preparation.decorators import test


def get_new_access_token():
    """
    Usando el RefreshToken, obtenemos un access token
    """
    client_id = get_secret_value('QBO_CLIENT_ID')
    client_secret = get_secret_value('QBO_CLIENT_SECRET')
    refresh_token = get_secret_value('QBO_REFRESH_TOKEN')

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_header}'
    }
    
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }
    
    # Endpoint de Sandbox
    url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
    
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Error renovando token: {response.text}")
        
    tokens_dict = response.json()
    
    new_refresh_token = tokens_dict.get('refresh_token')
    
    if new_refresh_token and new_refresh_token != refresh_token:
        print(f"⚠️ AVISO DE ROTACIÓN: Intuit ha entregado un nuevo Refresh Token.")
        print(f"Nuevo Token para actualizar en Secrets: {new_refresh_token}")
    
    # 4. Retornamos el access token como siempre
    return tokens_dict['access_token']

@data_loader
def load_data_from_api(*args, **kwargs):
    """
    Extrae Invoices de QBO usando paginación y filtros de fecha.
    """
    # 1. Obtener Access Token fresco
    access_token = get_new_access_token()
    realm_id = get_secret_value('QBO_REALM_ID')
    
    # 2. Configurar Entorno (Sandbox)
    base_url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    
    # 3. Leer Parámetros del Pipeline
    # Formato esperado: 'YYYY-MM-DD'
    start_date = kwargs['fecha_inicio']
    end_date = kwargs['fecha_fin']
    
    print(f"--- Iniciando extracción de Invoices desde {start_date} hasta {end_date} ---")

    all_invoices = []
    start_position = 1
    max_results = 100 # Máximo permitido por QBO es 1000, usamos 100 para probar paginación segura
    has_more_data = True
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Content-Type': 'application/text' # QBO Query usa text/plain
    }

    # 4. Bucle de Paginación
    while has_more_data:
        # Query SQL de QBO (Filtro por MetaData.LastUpdatedTime)
        # Nota: Convertimos las fechas a formato ISO simple para la query
        query = (
            f"SELECT * FROM Invoice "
            f"WHERE MetaData.LastUpdatedTime >= '{start_date}T00:00:00-05:00' "
            f"AND MetaData.LastUpdatedTime <= '{end_date}T23:59:59-05:00' "
            f"STARTPOSITION {start_position} MAXRESULTS {max_results}"
        )
        
        response = requests.post(base_url, headers=headers, data=query)
        
        if response.status_code == 429:
            print("Rate Limit alcanzado. Esperando 5 segundos...")
            time.sleep(5)
            continue
            
        if response.status_code != 200:
            raise Exception(f"Error en API QBO: {response.text}")
            
        data = response.json()
        query_response = data.get('QueryResponse', {})
        invoices = query_response.get('Invoice', [])
        
        if not invoices:
            print("No se encontraron más registros.")
            has_more_data = False
        else:
            print(f"Pagina extraida: {len(invoices)} invoices. StartPos: {start_position}")
            
            # 5. Transformación ligera para capa RAW
            # Preparamos la estructura que irá a Postgres
            for inv in invoices:
                row = {
                    'id': inv['Id'], # PK requerida
                    'payload': json.dumps(inv), # JSON completo requerido
                    'ingested_at_utc': datetime.utcnow().isoformat(), # Metadata requerida
                    'extract_window_start_utc': start_date,
                    'extract_window_end_utc': end_date,
                    'page_number': (start_position // max_results) + 1
                }
                all_invoices.append(row)
            
            start_position += len(invoices)
            
            # Si devolvió menos del máximo, es la última página
            if len(invoices) < max_results:
                has_more_data = False

    # Retornamos un DataFrame (formato nativo de Mage)
    print(f"Extracción total: {len(all_invoices)} registros.")
    return pd.DataFrame(all_invoices)


@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
