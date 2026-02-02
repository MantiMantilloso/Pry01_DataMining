# 🔄 QBO Data Pipeline - Backfill de QuickBooks Online

Pipeline de extracción de datos desde QuickBooks Online (Sandbox) hacia PostgreSQL utilizando Mage.ai como orquestador.

---

## 📑 Tabla de Contenidos

1. [Descripción del Proyecto](#-descripción-del-proyecto)
2. [Arquitectura](#-arquitectura)
3. [Requisitos Previos](#-requisitos-previos)
4. [Instalación y Configuración](#-instalación-y-configuración)
5. [Gestión de Secretos](#-gestión-de-secretos)
6. [Pipelines de Backfill](#-pipelines-de-backfill)
7. [Triggers One-Time](#-triggers-one-time)
8. [Esquema RAW de Base de Datos](#-esquema-raw-de-base-de-datos)
9. [Validaciones y Volumetría](#-validaciones-y-volumetría)
10. [Troubleshooting](#-troubleshooting)
11. [Evidencias](#-evidencias)
12. [Checklist de Aceptación](#-checklist-de-aceptación)

---

## 📋 Descripción del Proyecto

Este proyecto implementa un sistema de **backfill** (carga histórica) de datos desde la API de QuickBooks Online hacia una base de datos PostgreSQL. Se extraen tres entidades principales:

| Entidad | Descripción | Pipeline |
|---------|-------------|----------|
| **Customers** | Clientes registrados en QBO | `qb_customers_backfill` |
| **Invoices** | Facturas emitidas | `qb_invoices_backfill` |
| **Items** | Productos y servicios | `qb_items_backfill` |

### Características Principales
- ✅ Extracción con paginación automática
- ✅ Manejo de rate limits (429)
- ✅ Idempotencia mediante UPSERT
- ✅ Filtros por ventana de fechas
- ✅ Almacenamiento de payload completo en JSONB
- ✅ Metadatos de auditoría

---

## 🏗️ Arquitectura

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           ARQUITECTURA DEL SISTEMA                       │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
    │   QuickBooks     │         │     Mage.ai      │         │   PostgreSQL     │
    │   Online API     │────────▶│   (Orquestador)  │────────▶│   (raw schema)   │
    │   (Sandbox)      │         │   Puerto: 6789   │         │   Puerto: 5432   │
    └──────────────────┘         └──────────────────┘         └──────────────────┘
           │                            │                            │
           │                            │                            │
           ▼                            ▼                            ▼
    ┌──────────────────┐         ┌──────────────────┐         ┌──────────────────┐
    │  OAuth 2.0       │         │  - Data Loaders  │         │  - qb_customers  │
    │  - Access Token  │         │  - Data Exporters│         │  - qb_invoices   │
    │  - Refresh Token │         │  - Triggers      │         │  - qb_items      │
    └──────────────────┘         └──────────────────┘         └──────────────────┘
                                        │
                                        ▼
                                 ┌──────────────────┐
                                 │    PgAdmin 4     │
                                 │   Puerto: 8085   │
                                 └──────────────────┘
```

### Servicios Docker

| Servicio | Contenedor | Puerto | Descripción |
|----------|------------|--------|-------------|
| PostgreSQL | `qbo_postgres` | 5432 | Base de datos destino (esquema `raw`) |
| Mage.ai | `qbo_mage` | 6789 | Orquestador de pipelines ETL |
| PgAdmin | `qbo_pgadmin` | 8085 | Interfaz web para PostgreSQL |

### Red Docker
Todos los servicios están conectados a la red `qbo_network` (bridge), lo que permite comunicación por nombre de servicio.

---

## 📦 Requisitos Previos

- **Docker Desktop** instalado y ejecutándose
- **Git** para clonar el repositorio
- **Cuenta de desarrollador en Intuit** (QuickBooks Online Sandbox)
- Credenciales OAuth 2.0 de QBO (ver sección de Secretos)

---

## 🚀 Instalación y Configuración

### Paso 1: Clonar el Repositorio
```bash
git clone https://github.com/MantiMantilloso/Pry01_DataMining.git
cd Pry01_DataMining
```

### Paso 2: Crear archivo `.env`
Copiar la plantilla y completar con las credenciales:

```bash
# Windows
copy .env.example .env

# Linux/Mac
cp .env.example .env
```

Editar `.env` con las credenciales correspondientes:
```dotenv
# PostgreSQL
POSTGRES_USER=postgresroot
POSTGRES_PASSWORD=password123
POSTGRES_DB=qbo_raw_db

# PgAdmin
PGADMIN_EMAIL=admin@admin.com
PGADMIN_PASSWORD=admin
```

### Paso 3: Levantar los Contenedores
```bash
docker-compose up -d
```

### Paso 4: Verificar que los Servicios estén Corriendo
```bash
docker-compose ps
```

Resultado esperado:
```
NAME          STATUS                   PORTS
qbo_mage      Up                       0.0.0.0:6789->6789/tcp
qbo_pgadmin   Up                       0.0.0.0:8085->80/tcp
qbo_postgres  Up (healthy)             0.0.0.0:5432->5432/tcp
```

### Paso 5: Acceder a las Interfaces

| Servicio | URL | Credenciales |
|----------|-----|--------------|
| Mage.ai | http://localhost:6789 | Sin autenticación |
| PgAdmin | http://localhost:8085 | Definidas en `.env` |

### Paso 6: Configurar Conexión en PgAdmin
1. Click derecho en "Servers" → "Register" → "Server"
2. **General Tab**: Name = `QBO_Postgres`
3. **Connection Tab**:
   - Host: `postgres` (nombre del servicio Docker)
   - Port: `5432`
   - Database: `qbo_raw_db`
   - Username: `postgresroot`
   - Password: `password123`

---

## 🔐 Gestión de Secretos

### Ubicación de Secretos
Los secretos se gestionan mediante definidas en el archivo `.env` (no versionado), ademas las credenciales del servicio de API están almacenadas en `MAGE SECRETS`

### Inventario de Secretos

| Nombre | Propósito | Rotación | Responsable |
|--------|-----------|----------|-------------|
| `POSTGRES_USER` | Usuario de conexión a PostgreSQL | Manual, al crear el ambiente | DevOps/Admin |
| `POSTGRES_PASSWORD` | Contraseña de PostgreSQL | Cada 90 días recomendado | DevOps/Admin |
| `POSTGRES_DB` | Nombre de la base de datos | N/A (fijo) | DevOps/Admin |
| `QBO_CLIENT_ID` | Identificador de app en Intuit | N/A (fijo por app) | Developer QBO |
| `QBO_CLIENT_SECRET` | Secreto de la app OAuth | Al regenerar en Intuit Portal | Developer QBO |
| `QBO_REALM_ID` | ID de la compañía en QBO | N/A (fijo por compañía) | Developer QBO |
| `QBO_REFRESH_TOKEN` | Token para renovar access token | **Cada 100 días** (auto-rotación) | Pipeline/Manual |
| `PGADMIN_EMAIL` | Email de acceso a PgAdmin | N/A | Admin |
| `PGADMIN_PASSWORD` | Contraseña de PgAdmin | Al criterio del admin | Admin |

### ⚠️ Rotación del Refresh Token de QBO
El `QBO_REFRESH_TOKEN` tiene una validez de **100 días**. Intuit puede rotar el token automáticamente en cada uso.

**Procedimiento de Rotación:**
1. El pipeline detecta si Intuit envía un nuevo refresh token
2. Se imprime un mensaje de advertencia en los logs:
   ```
   ⚠️ AVISO DE ROTACIÓN: Nuevo Refresh Token detectado: <nuevo_token>
   ```
3. **Acción Manual Requerida**: Actualizar el valor en `MAGE SECRETS`

### Seguridad
- ✅ Usar `.env.example` como plantilla 
- ✅ Los secretos se pasan al contenedor de Mage vía environment en `docker-compose.yaml`

---

## 🔄 Pipelines de Backfill

### Estructura General

Cada pipeline sigue la arquitectura:
```
[Data Loader] ──▶ [Data Exporter]
   extract_*         export_*
```

### Pipeline: `qb_customers_backfill`

| Atributo | Valor |
|----------|-------|
| **Entidad** | Customer |
| **Data Loader** | `extract_customers.py` |
| **Data Exporter** | `export_customers.py` |
| **Tabla Destino** | `raw.qb_customers` |

### Pipeline: `qb_invoices_backfill`

| Atributo | Valor |
|----------|-------|
| **Entidad** | Invoice |
| **Data Loader** | `extract_invoices.py` |
| **Data Exporter** | `export_invoices.py` |
| **Tabla Destino** | `raw.qb_invoices` |

### Pipeline: `qb_items_backfill`

| Atributo | Valor |
|----------|-------|
| **Entidad** | Item |
| **Data Loader** | `extract_items.py` |
| **Data Exporter** | `export_items.py` |
| **Tabla Destino** | `raw.qb_items` |

### Parámetros de Ejecución

| Parámetro | Tipo | Formato | Descripción |
|-----------|------|---------|-------------|
| `fecha_inicio` | String | `YYYY-MM-DD` | Inicio de la ventana de extracción |
| `fecha_fin` | String | `YYYY-MM-DD` | Fin de la ventana de extracción |

**Ejemplo de configuración en trigger:**
```yaml
variables:
  fecha_inicio: '2014-01-01'
  fecha_fin: '2025-12-31'
```

### Segmentación del Rango
Los pipelines filtran por `MetaData.LastUpdatedTime` de QBO, usando la ventana definida:
```sql
WHERE MetaData.LastUpdatedTime >= '{fecha_inicio}T00:00:00-05:00'
  AND MetaData.LastUpdatedTime <= '{fecha_fin}T23:59:59-05:00'
```

### Paginación

| Configuración | Valor |
|---------------|-------|
| Tamaño de página | 100 registros |
| Máximo permitido por QBO | 1000 registros |
| Implementación | `STARTPOSITION` + `MAXRESULTS` |

```python
query = f"SELECT * FROM {entity} ... STARTPOSITION {start_position} MAXRESULTS 100"
```

### Rate Limits y Reintentos

| Escenario | Manejo |
|-----------|--------|
| HTTP 429 (Too Many Requests) | Espera 5 segundos y reintenta automáticamente |
| Error de conexión | Falla el pipeline, requiere re-ejecución manual |
| Error de autenticación | Falla inmediatamente, revisar tokens |

```python
if response.status_code == 429:
    print("Rate Limit. Esperando 5s...")
    time.sleep(5)
    continue
```

### Runbook de Reanudación

#### Escenario: Pipeline falló a mitad de ejecución

1. **Identificar el error** en logs de Mage:
   ```
   http://localhost:6789 → Pipeline → Logs
   ```

2. **Verificar registros ya insertados** en PostgreSQL:
   ```sql
   SELECT COUNT(*), MIN(ingested_at_utc), MAX(ingested_at_utc)
   FROM raw.qb_<entidad>;
   ```

3. **Re-ejecutar el pipeline** con los mismos parámetros:
   - La idempotencia garantiza que no habrá duplicados
   - Los registros existentes se actualizarán (UPSERT)

4. **Si el error es de autenticación (401)**:
   - Regenerar tokens en [Intuit Playground](https://developer.intuit.com/app/developer/playground)
   - Actualizar `QBO_REFRESH_TOKEN` en `.env`
   - Reiniciar Mage: `docker-compose restart mage`

#### Escenario: Backfill parcial (por tramos)

Para backfills muy grandes, segmentar por años:
```
Tramo 1: fecha_inicio=2014-01-01, fecha_fin=2018-12-31
Tramo 2: fecha_inicio=2019-01-01, fecha_fin=2022-12-31
Tramo 3: fecha_inicio=2023-01-01, fecha_fin=2025-12-31
```

---

## ⏰ Triggers One-Time

### Configuración

Los pipelines tienen triggers de tipo `@once` (una sola ejecución programada).

| Pipeline | Trigger Name | Schedule |
|----------|--------------|----------|
| `qb_customers_backfill` | `customers_trigger` | `@once` |
| `qb_invoices_backfill` | `invoice_trigger` | `@once` |
| `qb_items_backfill` | `items_trigger` | `@once` |

### Fecha/Hora de Ejecución

| Pipeline | UTC | Guayaquil (UTC-5) |
|----------|-----|-------------------|
| `qb_invoices_backfill` | 2026-02-02 00:00:00 | 2026-02-01 19:00:00 |
| `qb_customers_backfill` | 2026-02-02 00:02:00 | 2026-02-01 19:02:00 |
| `qb_items_backfill` | 2026-02-02 00:06:00 | 2026-02-01 19:06:00 |

### Política de Deshabilitación Post-Ejecución

1. **Ejecución Automática**: El trigger se ejecuta en la fecha/hora configurada
2. **Verificación**: Confirmar ejecución exitosa en Mage UI (estado "completed")
3. **Deshabilitación**: Cambiar `status: active` → `status: inactive` en:
   ```
   mage_data/qbo_project/pipelines/<pipeline>/triggers.yaml
   ```
   
   O desde la UI de Mage: Pipeline → Triggers → Disable

4. **Documentar**: Registrar fecha/hora de ejecución y resultado

### Ejemplo de Trigger Deshabilitado
```yaml
triggers:
- name: customers_trigger
  schedule_interval: '@once'
  status: inactive  # Cambiado de 'active' después de ejecución exitosa
  variables:
    fecha_inicio: '2014-01-01'
    fecha_fin: '2025-12-31'
```

---

## 🗄️ Esquema RAW de Base de Datos

### Esquema: `raw`

El esquema `raw` almacena los datos extraídos en su forma original (payload completo) más metadatos de auditoría.

### Tabla: `raw.qb_customers`

| Columna | Tipo | Restricción | Descripción |
|---------|------|-------------|-------------|
| `id` | VARCHAR(50) | **PRIMARY KEY** | ID único del cliente en QBO |
| `payload` | JSONB | NOT NULL | Datos completos del cliente |
| `ingested_at_utc` | TIMESTAMP | NOT NULL | Fecha/hora de ingestión (UTC) |
| `extract_window_start_utc` | VARCHAR(50) | | Inicio de ventana de extracción |
| `extract_window_end_utc` | VARCHAR(50) | | Fin de ventana de extracción |
| `page_number` | INTEGER | | Número de página de la extracción |

### Tabla: `raw.qb_invoices`

| Columna | Tipo | Restricción | Descripción |
|---------|------|-------------|-------------|
| `id` | VARCHAR(50) | **PRIMARY KEY** | ID único de la factura en QBO |
| `payload` | JSONB | NOT NULL | Datos completos de la factura |
| `ingested_at_utc` | TIMESTAMP | NOT NULL | Fecha/hora de ingestión (UTC) |
| `extract_window_start_utc` | VARCHAR(50) | | Inicio de ventana de extracción |
| `extract_window_end_utc` | VARCHAR(50) | | Fin de ventana de extracción |
| `page_number` | INTEGER | | Número de página de la extracción |

### Tabla: `raw.qb_items`

| Columna | Tipo | Restricción | Descripción |
|---------|------|-------------|-------------|
| `id` | VARCHAR(50) | **PRIMARY KEY** | ID único del item en QBO |
| `payload` | JSONB | NOT NULL | Datos completos del item |
| `ingested_at_utc` | TIMESTAMP | NOT NULL | Fecha/hora de ingestión (UTC) |
| `extract_window_start_utc` | VARCHAR(50) | | Inicio de ventana de extracción |
| `extract_window_end_utc` | VARCHAR(50) | | Fin de ventana de extracción |
| `page_number` | INTEGER | | Número de página de la extracción |

### Idempotencia

La idempotencia se garantiza mediante **UPSERT** (`INSERT ... ON CONFLICT DO UPDATE`):

```sql
INSERT INTO raw.qb_<entidad> (id, payload, ingested_at_utc, ...)
VALUES (:id, :payload, :ingested_at_utc, ...)
ON CONFLICT (id) DO UPDATE SET
    payload = EXCLUDED.payload,
    ingested_at_utc = EXCLUDED.ingested_at_utc,
    ...;
```

**Comportamiento:**
- Si el `id` no existe → INSERT nuevo registro
- Si el `id` ya existe → UPDATE con los nuevos valores
- **Resultado**: Re-ejecutar un pipeline nunca genera duplicados

### DDL de Creación

```sql
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.qb_customers (
    id VARCHAR(50) PRIMARY KEY,
    payload JSONB NOT NULL,
    ingested_at_utc TIMESTAMP NOT NULL,
    extract_window_start_utc VARCHAR(50),
    extract_window_end_utc VARCHAR(50),
    page_number INTEGER
);

CREATE TABLE IF NOT EXISTS raw.qb_invoices (
    id VARCHAR(50) PRIMARY KEY,
    payload JSONB NOT NULL,
    ingested_at_utc TIMESTAMP NOT NULL,
    extract_window_start_utc VARCHAR(50),
    extract_window_end_utc VARCHAR(50),
    page_number INTEGER
);

CREATE TABLE IF NOT EXISTS raw.qb_items (
    id VARCHAR(50) PRIMARY KEY,
    payload JSONB NOT NULL,
    ingested_at_utc TIMESTAMP NOT NULL,
    extract_window_start_utc VARCHAR(50),
    extract_window_end_utc VARCHAR(50),
    page_number INTEGER
);
```

---

## 📊 Validaciones y Volumetría

### Consultas de Volumetría

Ejecutar en PgAdmin o cualquier cliente PostgreSQL:

```sql
-- Conteo total por entidad
SELECT 'customers' as entidad, COUNT(*) as registros FROM raw.qb_customers
UNION ALL
SELECT 'invoices', COUNT(*) FROM raw.qb_invoices
UNION ALL
SELECT 'items', COUNT(*) FROM raw.qb_items;

-- Volumetría por ventana de extracción
SELECT 
    extract_window_start_utc,
    extract_window_end_utc,
    COUNT(*) as registros,
    MIN(ingested_at_utc) as primera_ingestion,
    MAX(ingested_at_utc) as ultima_ingestion
FROM raw.qb_customers
GROUP BY extract_window_start_utc, extract_window_end_utc;
```

### Validación de Idempotencia

```sql
-- Verificar que no hay duplicados (debe retornar 0 filas)
SELECT id, COUNT(*) 
FROM raw.qb_customers 
GROUP BY id 
HAVING COUNT(*) > 1;

-- Verificar integridad del payload
SELECT id, payload IS NOT NULL as tiene_payload
FROM raw.qb_customers
WHERE payload IS NULL;
```

### Validación de Metadatos

```sql
-- Verificar que todos los registros tienen metadatos completos
SELECT 
    COUNT(*) as total,
    COUNT(ingested_at_utc) as con_fecha_ingestion,
    COUNT(extract_window_start_utc) as con_ventana_inicio,
    COUNT(extract_window_end_utc) as con_ventana_fin
FROM raw.qb_customers;
```

### Interpretación de Resultados

| Validación | Resultado Esperado | Acción si Falla |
|------------|-------------------|-----------------|
| Conteo total | > 0 registros | Verificar ejecución del pipeline |
| Sin duplicados | 0 filas retornadas | Revisar lógica de UPSERT |
| Payload no nulo | 0 filas con NULL | Revisar extracción de API |
| Metadatos completos | Todos los conteos iguales | Revisar transformación |

---

## 🔧 Troubleshooting

### Errores de Autenticación (401 Unauthorized)

**Síntoma:**
```
Error en API QBO: {"fault":{"error":[{"code":"3200","message":"message=AuthenticationFailed"}]}}
```

**Causas y Soluciones:**

| Causa | Solución |
|-------|----------|
| Refresh Token expirado (>100 días) | Regenerar en [Intuit Playground](https://developer.intuit.com/app/developer/playground) |
| Client ID/Secret incorrectos | Verificar en Intuit Developer Portal |
| Realm ID incorrecto | Verificar el Company ID en QBO |

**Pasos:**
1. Ir a https://developer.intuit.com/app/developer/playground
2. Conectar con la cuenta de sandbox
3. Copiar el nuevo `refresh_token`
4. Actualizar en `.env`
5. Reiniciar Mage: `docker-compose restart mage`

### Errores de Paginación

**Síntoma:** El pipeline extrae menos registros de los esperados

**Verificación:**
```python
# En los logs debe aparecer:
"Pagina extraida: 100 <entidad>. StartPos: 1"
"Pagina extraida: 100 <entidad>. StartPos: 101"
# ... hasta que len < 100
```

**Solución:** Verificar que la query incluye `STARTPOSITION` y `MAXRESULTS`

### Rate Limits (429 Too Many Requests)

**Síntoma:**
```
Rate Limit alcanzado. Esperando 5 segundos...
```

**Comportamiento:** El pipeline maneja automáticamente este error con reintentos.

**Si persiste:**
- Reducir `max_results` de 100 a 50
- Aumentar el tiempo de espera de 5s a 60s
- Esperar unos minutos y re-ejecutar

### Problemas de Timezone

**Síntoma:** Los datos no coinciden con las fechas esperadas

**Contexto:**
- QBO API usa la timezone de la compañía (generalmente UTC-5 para Ecuador)
- La query usa offset `-05:00` para Guayaquil:
  ```sql
  WHERE MetaData.LastUpdatedTime >= '2024-01-01T00:00:00-05:00'
  ```

**Solución:** Ajustar el offset según la timezone de la compañía en QBO.

### Errores de Conexión a PostgreSQL

**Síntoma:**
```
could not connect to server: Connection refused
```

**Verificaciones:**

1. **Verificar que PostgreSQL está corriendo:**
   ```bash
   docker-compose ps
   ```

2. **Verificar nombre de host:**
   - Debe ser `postgres` (nombre del servicio), NO `localhost`

3. **Verificar red Docker:**
   ```bash
   docker network inspect pry01_qbo_network
   ```

4. **Verificar logs de PostgreSQL:**
   ```bash
   docker logs qbo_postgres
   ```

### Problemas de Almacenamiento

**Síntoma:** Error de disco lleno o PostgreSQL no inicia

**Verificación:**
```bash
# Ver tamaño de volúmenes
du -sh postgres_data/
du -sh mage_data/
```

**Solución:**
1. Limpiar datos de prueba si es necesario
2. Aumentar espacio en disco
3. En casos extremos, recrear el volumen:
   ```bash
   docker-compose down -v
   docker-compose up -d
   ```
   ⚠️ Esto borra todos los datos

### Permisos en Volúmenes (Linux/Mac)

**Síntoma:** Permission denied al escribir en volúmenes

**Solución:**
```bash
sudo chown -R $USER:$USER postgres_data/
sudo chown -R $USER:$USER mage_data/
sudo chown -R $USER:$USER pgadmin_data/
```

---

## 📸 Evidencias

Las evidencias del proyecto se encuentran en la carpeta `/evidencias/`:

| Evidencia | Archivo | Descripción |
|-----------|---------|-------------|
| Mage Secrets | `mage_secrets.png` | Configuración de secretos (nombres visibles, valores ocultos) |
| Trigger Configurado | `trigger_config.png` | Triggers one-time configurados |
| Ejecución Finalizada | `trigger_completed.png` | Estado de ejecución completada |
| Tablas RAW | `raw_tables.png` | Registros en PostgreSQL con metadatos |
| Volumetría | `volumetria.png` | Reporte de conteo por entidad |
| Idempotencia | `idempotencia.png` | Query de verificación sin duplicados |

---

## ✅ Checklist de Aceptación

- [x] **Mage y Postgres se comunican por nombre de servicio.**
  - Host configurado como `postgres` en los exporters y docker-compose

- [x] **Todos los secretos (QBO y Postgres) están en variables de entorno; no hay secretos en el repo/entorno expuesto.**
  - Secretos en `.env` (no versionado)
  - `.env.example` como plantilla (sin valores reales)
  - Scripts usan `os.environ.get()`

- [x] **Pipelines `qb_<entidad>_backfill` acepta `fecha_inicio` y `fecha_fin` (UTC) y segmenta el rango.**
  - Parámetros configurados en triggers.yaml
  - Query filtra por `MetaData.LastUpdatedTime`

- [x] **Trigger one-time configurado, ejecutado y luego deshabilitado/marcado como completado.**
  - Schedule: `@once`
  - Post-ejecución: cambiar status a `inactive`

- [x] **Esquema `raw` con tablas por entidad, payload completo y metadatos obligatorios.**
  - Tablas: `raw.qb_customers`, `raw.qb_invoices`, `raw.qb_items`
  - Payload en JSONB
  - Metadatos: `ingested_at_utc`, `extract_window_*`, `page_number`

- [x] **Idempotencia verificada: reejecución de un tramo no genera duplicados.**
  - Implementado con `ON CONFLICT (id) DO UPDATE`
  - Query de verificación documentada

- [x] **Paginación y rate limits manejados y documentados.**
  - Paginación: `STARTPOSITION` + `MAXRESULTS`
  - Rate limit: sleep 5s en HTTP 429

- [x] **Volumetría y validaciones mínimas registradas y archivadas como evidencia.**
  - Queries de validación documentadas
  - Evidencias en carpeta `/evidencias/`

- [x] **Runbook de reanudación y reintentos disponible y seguido.**
  - Documentado en sección de Pipelines
  - Procedimientos para escenarios de falla

---

## 👤 Información del Proyecto

| Campo | Valor |
|-------|-------|
| **Autor** | Mauricio Mantilla |
| **Curso** | Data Mining |
| **Universidad** | USFQ |
| **Repositorio** | https://github.com/MantiMantilloso/Pry01_DataMining |

---

## 📁 Estructura del Repositorio

```
Pry01_DataMining/
├── 📄 docker-compose.yaml        # Definición de servicios Docker
├── 📄 .env.example               # Plantilla de variables de entorno
├── 📄 README.md                  # Este archivo
├── 📁 mage_data/                 # Volumen de Mage AI
│   └── qbo_project/
│       ├── pipelines/
│       │   ├── qb_customers_backfill/
│       │   ├── qb_invoices_backfill/
│       │   └── qb_items_backfill/
│       ├── data_loaders/
│       │   ├── extract_customers.py
│       │   ├── extract_invoices.py
│       │   └── extract_items.py
│       └── data_exporters/
│           ├── export_customers.py
│           ├── export_invoices.py
│           └── export_items.py
├── 📁 postgres_data/             # Volumen de PostgreSQL
├── 📁 pgadmin_data/              # Volumen de PgAdmin
└── 📁 evidencias/                # Capturas y evidencias
    ├── mage_secrets.png
    ├── trigger_config.png
    ├── trigger_completed.png
    ├── raw_tables.png
    ├── volumetria.png
    └── idempotencia.png
```
