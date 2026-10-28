# Campus Eats – Backend

API en FastAPI + SQLAlchemy con **PostgreSQL alojado en Supabase**. La app Kotlin solo habla con la API por HTTP; nunca con la base de datos. Todo el equipo usa la misma base en la nube, así que los datos son compartidos.

```
App Kotlin ─ HTTP ─> API FastAPI (tu PC, puerto 8001) ─> PostgreSQL en Supabase
```

La API se ejecuta en tu computador y se conecta a Supabase con la variable `DATABASE_URL`. La documentación de todas las rutas está en `http://127.0.0.1:8001/docs` con la API corriendo.

Los comandos son para el **Símbolo del sistema (CMD)** de Windows.

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
DATABASE_URL=postgresql://postgres.rxupinvdiydqkjrrvyen:CampusEatsISIS3510*@aws-1-us-west-2.pooler.supabase.com:5432/postgres?sslmode=require
JWT_SECRET=cualquier-texto-largo-que-inventes
ANALYTICS_ADMIN_EMAILS=demo01@uniandes.edu.co
```

`.env` está en `.gitignore`: nunca lo subas.

## 4. Ejecutar la API

```bat
cd /d <ruta>\Backend
venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8001
```

Déjala abierta mientras uses las apps. Comprueba en el navegador:

- http://127.0.0.1:8001/ debe responder `{"status":"ok", ...}`.
- http://127.0.0.1:8001/docs muestra la documentación.
- http://127.0.0.1:8001/analytics/search-gaps debe devolver datos de la base de Supabase.

## 5. App Kotlin

1. En el archivo `%USERPROFILE%\.gradle\gradle.properties` debe existir (una sola vez) esta línea:

```
apiBaseUrl=http\://localhost:8001
```

```bat
notepad "%USERPROFILE%\.gradle\gradle.properties"
```

2. Abre el emulador y conecta el puerto:

```bat
start "" "%LOCALAPPDATA%\Android\Sdk\emulator\emulator.exe" -avd Medium_Phone_API_37.0 -no-snapshot-load
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" wait-for-device
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" devices
"%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe" reverse tcp:8001 tcp:8001
```

`adb devices` debe mostrar `emulator-5554  device` (no `offline`). Con un celular por USB, activa la depuración USB y ejecuta solo el último comando (`adb reverse`).

3. En **Android Studio** abre `App_Kotlin`, elige el dispositivo y pulsa **Run ▶**.

4. Tests unitarios:

```bat
cd /d <ruta>\App_Kotlin
gradlew.bat :app:testDebugUnitTest --rerun
```

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
| La app no conecta a la API | La API no está corriendo, o falta `adb reverse tcp:8001 tcp:8001` |
| El emulador se queda en `offline` | Ciérralo y ábrelo con `-no-snapshot-load`, como en el paso 5 |
| `pip` con `CERTIFICATE_VERIFY_FAILED` | Agrega `--use-feature=truststore` |
