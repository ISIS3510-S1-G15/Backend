# Campus Eats – Backend

API en FastAPI + SQLAlchemy con **PostgreSQL alojado en Supabase**, desplegada en **Railway**. Las apps solo hablan con la API por HTTPS; nunca con la base de datos. Todo el equipo usa la misma base en la nube, así que los datos son compartidos.

```
Apps Kotlin / Flutter ─ HTTPS ─> API FastAPI (Railway) ─> PostgreSQL en Supabase
```

URL pública: **https://backend-production-925d.up.railway.app**

- La API corre 24/7 en Railway: **no hace falta ejecutar el Backend en tu computador**. Solo se ejecutan las apps (Kotlin o Flutter).
- Cada push a la rama configurada en Railway redespliega la API automáticamente. Al arrancar aplica las migraciones de Alembic (`alembic upgrade head`).
- Documentación de las rutas: https://backend-production-925d.up.railway.app/docs
- Variables en Railway (no están en el repositorio): `DATABASE_URL`, `JWT_SECRET`, `ANALYTICS_ADMIN_EMAILS` y `PORT`.

Las secciones siguientes son solo para desarrollo local del Backend (opcional). Los comandos son para el **Símbolo del sistema (CMD)** de Windows.

## 1. Requisitos

- Python **3.11** (con 3.10 no instalan las dependencias).
- Git.

## 2. Instalación (una sola vez)

```bat
cd /d <ruta>\Backend
py -3.11 -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

Si `pip` falla con `CERTIFICATE_VERIFY_FAILED`, agrega `--use-feature=truststore` al final del comando de `pip install`.

## 3. Configurar la conexión (una sola vez)

Crea el archivo `.env` en la carpeta `Backend`:

```bat
notepad .env
```

Responde **Sí** si pide crearlo, pega estas líneas tal cual y guarda:

```
DATABASE_URL=postgresql://USUARIO:CLAVE@HOST_POOLER:5432/postgres?sslmode=require
JWT_SECRET=cualquier-texto-largo-que-inventes
ANALYTICS_ADMIN_EMAILS=demo01@uniandes.edu.co
```

USUARIO, CLAVE y HOST_POOLER se piden al equipo (no se publican en este repositorio).

`.env` está en `.gitignore`: nunca lo subas.

## 4. Ejecutar la API en local (opcional)

```bat
cd /d <ruta>\Backend
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Solo hace falta si vas a desarrollar el Backend. Comprueba en el navegador:

- http://127.0.0.1:8001/ debe responder `{"status":"ok", ...}`.
- http://127.0.0.1:8001/docs muestra la documentación.
- http://127.0.0.1:8001/analytics/search-gaps debe devolver datos de la base de Supabase.

## 5. Apps Kotlin y Flutter

Ambas apps usan por defecto la API de Railway; no necesitas configurar nada ni ejecutar el Backend. Solo ejecuta la app desde Android Studio (Kotlin) o con `flutter run` (Flutter). Los detalles están en el README de cada repositorio (`App_Kotlin` y `App_Flutter`).

Para apuntar a tu Backend local en lugar de Railway:

- Kotlin: agrega `apiBaseUrl=http\://localhost:8001` en `%USERPROFILE%\.gradle\gradle.properties` y ejecuta `adb reverse tcp:8001 tcp:8001`.
- Flutter: `flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8001`.

## 6. Usuarios y datos de demostración

La base ya tiene datos cargados para todas las preguntas de negocio. Para iniciar sesión en las apps puedes usar:

| Correo | Contraseña |
|---|---|
| `demo01@uniandes.edu.co` … `demo12@uniandes.edu.co` | `Demo1234!` |

`demo01@uniandes.edu.co` está listado como administrador de analítica (`ANALYTICS_ADMIN_EMAILS`), necesario para ver `/analytics/sections/usage` y `/analytics/sections/least-used`.

## Reglas de la base compartida

- No borres datos de Supabase ni ejecutes `pytest` con esta conexión (los tests se bloquean solos).
- No subas el archivo `.env` al repositorio.
- El plan gratuito de Supabase pausa el proyecto tras una semana sin uso: reactívalo desde su panel.

## Problemas comunes

| Mensaje o síntoma | Solución |
|---|---|
| `DATABASE_URL no esta definida` | Falta el archivo `.env` en la carpeta `Backend` |
| `password authentication failed` | La clave en `.env` está mal escrita |
| `Network is unreachable` o no conecta | La URL debe ser la del *pooler* (`aws-1-us-west-2.pooler.supabase.com`, puerto 5432) |
| `403 Analytics access denied` | Tu correo no está en `ANALYTICS_ADMIN_EMAILS` |
| La app no conecta a la API | Revisa que https://backend-production-925d.up.railway.app/ responda. Si usas un Backend local, falta `adb reverse tcp:8001 tcp:8001` |
| La app dice que no conecta y el certificado no es confiable | Un antivirus (por ejemplo Avast) intercepta HTTPS: desactiva el análisis HTTPS o agrega una excepción para `*.up.railway.app` |
| El emulador se queda en `offline` | Ciérralo y ábrelo con `-no-snapshot-load` |
| `pip` con `CERTIFICATE_VERIFY_FAILED` | Agrega `--use-feature=truststore` |
