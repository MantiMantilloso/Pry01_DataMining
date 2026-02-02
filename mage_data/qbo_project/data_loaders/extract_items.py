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

def get_new_access_token():
    # --- LOGICA DE ROTACION Y AUTH (IGUAL QUE ANTES) ---
    client_id = get_secret_value('QBO_CLIENT_ID')
    client_secret = get_secret_value('QBO_CLIENT_SECRET')
    refresh_token = get_secret_value('QBO_REFRESH_TOKEN')

    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth_header}'
    }
    
    data = {'grant_type': 'refresh_token', 'refresh_token': refresh_token}
    url = 'https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer'
    
    response = requests.post(url, headers=headers, data=data)
    
    if response.status_code != 200:
        raise Exception(f"Error renovando token: {response.text}")
        
    tokens_dict = response.json()
    new_refresh_token = tokens_dict.get('refresh_token')
    
    # Chequeo de rotación
    if new_refresh_token and new_refresh_token != refresh_token:
        print(f"⚠️ AVISO DE ROTACIÓN: Nuevo Refresh Token detectado: {new_refresh_token}")
    
    return tokens_dict['access_token']

@data_loader
def load_data_from_api(*args, **kwargs):
    """
    Extrae Items de QBO.
    """
    access_token = get_new_access_token()
    realm_id = get_secret_value('QBO_REALM_ID')
    base_url = f"https://sandbox-quickbooks.api.intuit.com/v3/company/{realm_id}/query"
    
    start_date = kwargs['fecha_inicio'] 
    end_date = kwargs['fecha_fin']
    
    print(f"--- Extrayendo ITEMS desde {start_date} hasta {end_date} ---")

    all_data = []
    start_position = 1
    max_results = 100
    has_more_data = True
    
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json',
        'Content-Type': 'application/text'
    }

    while has_more_data:
        # --- CAMBIO CLAVE: Query a la tabla Item ---
        query = (
            f"SELECT * FROM Item "
            f"WHERE MetaData.LastUpdatedTime >= '{start_date}T00:00:00-05:00' "
            f"AND MetaData.LastUpdatedTime <= '{end_date}T23:59:59-05:00' "
            f"STARTPOSITION {start_position} MAXRESULTS {max_results}"
        )
        
        response = requests.post(base_url, headers=headers, data=query)
        
        if response.status_code == 429:
            print("Rate Limit. Esperando 5s...")
            time.sleep(5)
            continue
            
        if response.status_code != 200:
            raise Exception(f"Error API: {response.text}")
            
        data = response.json()
        query_response = data.get('QueryResponse', {})
        # --- CAMBIO CLAVE: La llave ahora es 'Item' ---
        records = query_response.get('Item', [])
        
        if not records:
            has_more_data = False
        else:
            print(f"Pagina extraida: {len(records)} Items.")
            
            for item in records:
                row = {
                    'id': item['Id'],
                    'payload': json.dumps(item),
                    'ingested_at_utc': datetime.utcnow().isoformat(),
                    'extract_window_start_utc': start_date,
                    'extract_window_end_utc': end_date,
                    'page_number': (start_position // max_results) + 1
                }
                all_data.append(row)
            
            start_position += len(records)
            if len(records) < max_results:
                has_more_data = False

    print(f"Total Items: {len(all_data)}")
    return pd.DataFrame(all_data)

@test
def test_output(output, *args) -> None:
    """
    Template code for testing the output of the block.
    """
    assert output is not None, 'The output is undefined'
