# Campus Eats – Backend

API en FastAPI + SQLAlchemy 2 con **PostgreSQL**. Las apps (Kotlin y Flutter) solo hablan con la API por HTTP; nunca con la base de datos. El diseño de la base de datos, con diagramas, está en [docs/ARQUITECTURA_BD.md](docs/ARQUITECTURA_BD.md).

```
App Kotlin  ─┐
             ├─ HTTP ─> API FastAPI (puerto 8001) ─ SQLAlchemy/psycopg ─> PostgreSQL
App Flutter ─┘
```

- El esquema lo crea y versiona **Alembic** (`alembic/versions`). La app no crea tablas al arrancar.
- `DATABASE_URL` es obligatoria. Si falta o no es PostgreSQL, la app falla con un mensaje claro. **No hay fallback a SQLite.**
- `campus_eats.db` (SQLite) se conserva solo como origen de datos históricos que ya fueron importados.

## Estado actual

| Pieza | Estado |
|---|---|
| PostgreSQL local con Docker | Implementado y probado |
| Migración de los datos de SQLite (70 filas) | Hecha y verificada fila por fila, tanto en local como en Supabase |
| Base de datos compartida en **Supabase** | Operativa: la API local conectada a Supabase y la app Kotlin en emulador guardaron datos allí |
| Tests del Backend (29) y de Kotlin (53) | Ejecutados y pasando |
| API desplegada en línea (Render) | **Pendiente**: hoy cada integrante ejecuta la API en su PC |
| App Flutter contra esta API | **No probada** (no había Flutter SDK en la máquina donde se migró) |

## Dos formas de trabajar

| | A. Base compartida (Supabase) | B. Base local (Docker) |
|---|---|---|
| Dónde está PostgreSQL | En la nube, la misma para todo el equipo | En tu PC |
| Datos | Compartidos: lo que registra alguien lo ve el resto | Solo tuyos |
| Requiere | Python 3.11 y la clave de Supabase | Python 3.11 y Docker Desktop |
| Úsala para | Probar las apps con datos reales del equipo | Desarrollar, correr tests, experimentar sin afectar a nadie |

En ambos casos la API corre en tu PC en el puerto 8001. Lo único que cambia es `DATABASE_URL`.

## Requisitos

- **Python 3.11.** Las dependencias fijadas (por ejemplo `websockets==17.1`) no instalan en 3.10.
- Docker Desktop, solo para la forma B.

## Instalación (una vez)

```powershell
cd <ruta>\Backend
py -3.11 -m venv venv
venv\Scripts\python -m pip install -r requirements-dev.txt
copy .env.example .env
```

Si `pip` falla con `CERTIFICATE_VERIFY_FAILED` (redes con inspección TLS), agrega `--use-feature=truststore` al comando de `pip install`.

## A. Base compartida (Supabase)

1. Pide la clave de la base a quien administra el proyecto de Supabase, **por mensaje privado**. No está en el repositorio y no debe pegarse en chats grupales, issues ni commits.
2. Edita `.env` (está en `.gitignore`) y deja estas dos líneas, con la clave en lugar de `<CLAVE>`:

```
DATABASE_URL=postgresql://postgres.rxupinvdiydqkjrrvyen:<CLAVE>@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require
JWT_SECRET=<cualquier texto largo y aleatorio>
```

3. Arranca la API:

```powershell
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

4. Comprueba: <http://127.0.0.1:8001/> debe responder `{"status":"ok",...}` y <http://127.0.0.1:8001/docs> muestra la documentación.

Reglas de la base compartida:
- Las tablas ya existen y tienen datos. **No ejecutes el importador** contra ella.
- Si cambias los modelos, crea una migración con Alembic y aplícala una sola vez; avisa al equipo.
- **No ejecutes `pytest` con esta URL en `.env`.** Los tests lo detectan y se niegan, porque vacían tablas.
- Usa el *Session pooler* (puerto 5432) y no la conexión directa (solo IPv6) ni el *Transaction pooler* (puerto 6543, incompatible con el driver).
- El plan gratuito de Supabase pausa el proyecto tras una semana sin uso: reactívalo desde el panel.

## B. Base local (Docker)

```powershell
docker compose up -d db
docker compose ps
venv\Scripts\python -m alembic upgrade head
venv\Scripts\python -m scripts.import_sqlite campus_eats.db
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Con el `.env` creado desde `.env.example`, `DATABASE_URL` ya apunta a `127.0.0.1:5432` (usa `127.0.0.1` y no `localhost`: en Windows `localhost` puede tardar más de 30 s por IPv6). El importador es opcional y solo se ejecuta una vez; sin él empiezas con la base vacía.

### API dentro de Docker (opcional)

`docker compose up -d --build` también construye y levanta la API en el puerto 8001. Si el build falla con `CERTIFICATE_VERIFY_FAILED` al instalar paquetes, tu red intercepta TLS y el contenedor no confía en ese certificado: usa el flujo anterior (PostgreSQL en Docker, API local).

## Variables de entorno (`.env`)

| Variable | Uso |
|---|---|
| `DATABASE_URL` | Conexión de la API a PostgreSQL (Supabase o local) |
| `JWT_SECRET` | Firma de los tokens de sesión |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Solo forma B: credenciales del contenedor |
| `POSTGRES_HOST_PORT` | Solo forma B: puerto en tu PC (solo `127.0.0.1`), por defecto 5432 |
| `API_PORT` | Solo API en Docker: puerto, por defecto 8001 |

`.env` nunca se sube al repositorio. Si una clave tiene caracteres especiales debe ir codificada en la URL; lo más simple es usar claves de letras y números. Para generar una:

```powershell
-join ((1..32) | ForEach-Object { '{0:x}' -f (Get-Random -Maximum 16) })
```

## Esquema vs. datos

- **Crear o actualizar el esquema:** `alembic upgrade head`. Es seguro repetirlo.
- **Importar los datos históricos de SQLite (una sola vez por base):** `python -m scripts.import_sqlite campus_eats.db`. Se niega a importar si alguna tabla ya tiene filas, no borra nada, conserva ids, hashes bcrypt y fechas (UTC), ajusta las secuencias, compara fila por fila SQLite contra PostgreSQL y revisa llaves foráneas dentro de la misma transacción: cualquier discrepancia deshace todo. Con `--verify` solo compara.

## Datos de demostración para las BQ

`scripts/seed_demo_data.py` siembra datos coherentes para que todas las preguntas de negocio devuelvan resultados. Crea 12 usuarios `demo01@uniandes.edu.co` … `demo12@uniandes.edu.co` (contraseña `Demo1234!`) y reparte datos de las últimas 5 semanas con los mismos valores que envía la app Kotlin (restaurantes `1` a `4`, filtros, pantallas, franjas de comida y secciones).

| BQ | Tablas | Qué se siembra |
|---|---|---|
| Aperturas por semana (tipo 1) | `app_opens` | Unas 235 aperturas, 12 usuarios, 5 semanas, las 6 franjas de comida |
| Revisión de ocupación antes de ir (tipo 2) | `occupancy_events`, `occupancy_checks` | Revisiones y decisiones de ir, con y sin revisión previa en 30 min |
| Filtros más usados (tipo 2) | `filter_usages` | Filtros de `home`, `search` y `map`; el más usado es "Vegan options" |
| Onboarding completado (tipo 2) | `onboarding_events` | 40 sesiones con abandono por paso |
| Ediciones de preferencias (tipo 3) | `profile_edits` | 8 instalaciones; campos `dietary_restrictions` y `cuisine_preferences` |
| Búsquedas sin resultados (tipo 3) | `zero_result_searches` | 10 términos con frecuencias distintas |
| Guardados poco vistos (tipo 3) | `saved_restaurants`, `restaurant_views` | Los restaurantes `3` y `4` casi no se reabren; el `1` sí |
| Secciones menos usadas (tipo 3) | `section_events` | 340 visitas (mínimo 30 por sección): `filters` queda con baja interacción y `favorites` como nicho |

```powershell
venv\Scripts\python -m alembic upgrade head
venv\Scripts\python -m scripts.seed_demo_data --dry-run
venv\Scripts\python -m scripts.seed_demo_data
```

- Necesita el esquema en la última versión (`alembic upgrade head`).
- Se ejecuta en una sola transacción y **se niega a repetirse** si ya existen usuarios `demo##`.
- `--dry-run` calcula todo y no escribe nada. `--seed` y `--weeks` cambian la semilla y el periodo.
- Los endpoints `/analytics/sections/usage` y `/analytics/sections/least-used` exigen un usuario listado en la variable de entorno `ANALYTICS_ADMIN_EMAILS` de la API (por ejemplo `demo01@uniandes.edu.co`).
- No hay borrado automático. Las filas ligadas a usuarios demo se pueden quitar borrando esas filas y luego los usuarios; las tablas anónimas (`filter_usages`, `zero_result_searches`, `occupancy_checks`) no se pueden distinguir de datos reales, por eso conviene sembrar solo en bases de demostración.

## Cómo se hizo la migración de SQLite a PostgreSQL

1. **Respaldo** del `campus_eats.db` original antes de tocar nada (con su hash SHA-256). El archivo original no se modificó.
2. **Diagnóstico:** 11 tablas y 70 filas en SQLite; sin violaciones de llaves foráneas. El único SQL propio de SQLite era `strftime("%Y-%W", ...)` en los reportes semanales de aperturas (`/analytics/app-opens/weekly` y `/export`); ahora el agrupado por semana se calcula en Python con el mismo formato, así que el resultado es idéntico.
3. **Configuración:** `app/database.py` lee `DATABASE_URL`, valida que sea PostgreSQL (driver `psycopg` 3), usa `pool_pre_ping` y fija la sesión en UTC al conectar. Se eliminó la creación automática de tablas de `main.py`.
4. **Esquema versionado con Alembic:** `0001` crea las 13 tablas, llaves, restricciones e índices; `0002` activa *row level security* sin políticas, para que la base no sea legible por la API de datos de Supabase.
5. **Importador seguro** (`scripts/import_sqlite.py`): lee SQLite en solo lectura, exige el esquema en la última versión, se niega a importar si alguna tabla ya tiene filas, importa todo en una transacción, conserva ids, hashes bcrypt y fechas, ajusta las secuencias y compara fila por fila antes de confirmar. Cualquier discrepancia deshace todo.
6. **Resultado verificado:** 70 de 70 filas, tanto en el PostgreSQL local como en Supabase; 0 filas huérfanas; la siguiente secuencia de `users` es 5.
7. **Pruebas:** 29 pruebas del Backend (conexión, restricciones, autenticación, rutas protegidas, CRUD, rollback, importador, reportes) y 53 pruebas de Kotlin, incluida una de extremo a extremo contra la API real.

## Rutas de la API

La documentación interactiva completa está en `/docs`. "JWT" significa que requiere el encabezado `Authorization: Bearer <token>`.

| Grupo | Método y ruta | Acceso |
|---|---|---|
| Salud | `GET /` | Pública |
| Autenticación | `POST /auth/register`, `POST /auth/login` | Pública |
| | `GET /auth/me` | JWT |
| Perfil | `GET /me/profile`, `PUT /me/profile` | JWT |
| Guardados | `GET /me/saved`, `PUT /me/saved/{restaurant_id}`, `DELETE /me/saved/{restaurant_id}` | JWT |
| Reseñas | `GET /restaurants/{restaurant_id}/reviews`, `GET /reviews/summary` | Pública |
| | `POST /restaurants/{restaurant_id}/reviews` | JWT |
| Ocupación | `GET /occupancy`, `GET /occupancy/{restaurant_id}` | Pública |
| | `POST /occupancy/reports` | JWT |
| Analítica con usuario | `POST /analytics/app-open`, `POST /analytics/occupancy-event`, `POST /analytics/restaurant-view` | JWT |
| Analítica anónima (registro) | `POST /analytics/zero-result-search`, `/onboarding-event`, `/filter-usage`, `/occupancy-check`, `/profile-edit` | Pública |
| Analítica (reportes) | `GET /analytics/search-gaps`, `/onboarding-completion`, `/filter-usage`, `/occupancy-checks`, `/occupancy-check-rate`, `/profile-edits`, `/profile-edits/by-field`, `/app-opens/weekly`, `/saved-rarely-viewed` | Pública |
| Exportación CSV | Cada reporte anterior tiene su versión en `.../export` | Pública |

Las rutas, métodos, cuerpos y respuestas no cambiaron con la migración: las apps existentes funcionan sin modificarse.

## Tests (solo con la base local)

Usan una base aislada `<POSTGRES_DB>_test` en el PostgreSQL local de Docker (se crea sola). Se niegan a ejecutarse si `DATABASE_URL` apunta a un servidor remoto.

```powershell
docker compose up -d db
venv\Scripts\python -m pytest -q
```

## Apps móviles

La API corre en tu PC (puerto 8001). Un emulador o celular no ve el `localhost` de tu PC por sí mismo; hay dos mecanismos:

- `adb reverse tcp:8001 tcp:8001`: el dispositivo (emulador o celular por USB) usa `localhost:8001`.
- `10.0.2.2`: alias del PC anfitrión, solo en el emulador de Android.

Un celular físico por Wi-Fi necesitaría la IP LAN del PC y permitir esa dirección en la configuración de red de la app; por USB con `adb reverse` no hace falta.

**Kotlin (`App_Kotlin`)**: la URL sale de la propiedad Gradle `apiBaseUrl`. Configúrala sin duplicar líneas (PowerShell):

```powershell
$f = "$env:USERPROFILE\.gradle\gradle.properties"
if (-not (Test-Path $f)) { New-Item -ItemType File -Path $f -Force | Out-Null }
$lines = @(Get-Content $f | Where-Object { $_ -notmatch '^apiBaseUrl=' }) + 'apiBaseUrl=http\://localhost:8001'
Set-Content -Path $f -Value $lines -Encoding ascii
```

Luego abre el emulador (o conecta el celular), ejecuta `adb reverse tcp:8001 tcp:8001` y pulsa Run en Android Studio. Tests: `gradlew.bat :app:testDebugUnitTest --rerun`. El test `BackendEndToEndTest` solo corre si defines `ANALYTICS_E2E_URL`, y registra usuarios `e2e-*`: apúntalo a una API con base local, no a la compartida.

**Flutter (`App_Flutter`)**: la URL por defecto sigue siendo `http://10.0.2.2:8000`; para esta API se indica con `--dart-define`:

```powershell
flutter pub get
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001
```

## Despliegue en línea de la API (pendiente)

Para que los monitores prueben el APK en sus celulares, la API necesita una URL pública con HTTPS. El plan es **Render** (ejecuta la API a partir del `Dockerfile`, que ya respeta la variable `PORT`) usando la base de Supabase. Pasos, aún no ejecutados:

1. Fusionar los cambios a `main` y conectar el repositorio en Render (*New → Web Service*, runtime Docker, *Health Check Path* `/`).
2. Definir en Render las variables `DATABASE_URL` (la de Supabase) y `JWT_SECRET` (largo y distinto al de desarrollo).
3. Apuntar las apps a la URL pública: Kotlin con `apiBaseUrl=https\://<servicio>.onrender.com` y Flutter con `--dart-define=API_BASE_URL=https://<servicio>.onrender.com`.

En el plan gratuito la API se duerme tras un rato sin tráfico: la primera petición tarda 30–60 s.

## Inspeccionar y respaldar

Base local:

```powershell
docker compose exec db psql -U campus_eats -d campus_eats -c "\dt"
docker compose exec db pg_dump -U campus_eats -Fc -f /tmp/backup.dump campus_eats
docker compose cp db:/tmp/backup.dump .\backup.dump
docker compose cp .\backup.dump db:/tmp/backup.dump
docker compose exec db pg_restore -U campus_eats -d campus_eats --clean --if-exists /tmp/backup.dump
```

`--clean` borra y recrea objetos: úsalo solo sobre una base que quieras sobrescribir. En Supabase puedes ver y editar filas en *Table Editor*.

## Apagar y problemas comunes

```powershell
docker compose down
```

Nunca uses `docker compose down -v`: borra el volumen `pgdata` y **todos los datos locales**.

| Problema | Causa / solución |
|---|---|
| `DATABASE_URL no esta definida` | Falta `.env` o la variable |
| `SQLite ya no esta soportado` | `DATABASE_URL` apunta a SQLite |
| Conexión lenta (30 s) | Usa `127.0.0.1` en lugar de `localhost` en la forma B |
| `password authentication failed` | Clave de Supabase mal escrita o reseteada |
| `Network is unreachable` / no conecta a Supabase | Usaste la conexión directa; usa el *Session pooler* |
| La app móvil no conecta | La API no está corriendo, o falta `adb reverse tcp:8001 tcp:8001` |
| `CERTIFICATE_VERIFY_FAILED` en `pip` | `--use-feature=truststore`; en Docker, ver la sección de la API |
| `La base PostgreSQL ya contiene datos` | Protección anti-duplicados del importador; es lo esperado |
| Puerto 5432 ocupado | Cambia `POSTGRES_HOST_PORT` y la URL en `DATABASE_URL` |
| `invalid file request ...` al construir | Archivo de OneDrive "solo en la nube": clic derecho → *Mantener siempre en este dispositivo* |
