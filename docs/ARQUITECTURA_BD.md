# Arquitectura de la base de datos – Campus Eats

Documento basado en `app/models.py` y en las migraciones de `alembic/versions`. El motor es **PostgreSQL 16**.

## 1. Arquitectura general

Las apps solo hablan con la API por HTTP(S). Ninguna app recibe credenciales de la base de datos.

```mermaid
flowchart LR
    subgraph Clientes
        K[App Kotlin]
        F[App Flutter]
    end

    subgraph Servidor
        A[API FastAPI]
        M[Alembic<br/>migraciones]
    end

    DB[(PostgreSQL)]

    K -- HTTP/JSON + JWT --> A
    F -- HTTP/JSON + JWT --> A
    A -- SQLAlchemy + psycopg --> DB
    M -- esquema versionado --> DB
```

## 2. Entornos

```mermaid
flowchart TB
    subgraph Local["Desarrollo local (cada integrante)"]
        L1[uvicorn en el PC<br/>puerto 8001]
        L2[(PostgreSQL en Docker<br/>volumen pgdata)]
        L1 --> L2
    end

    subgraph Linea["Entorno en línea (entrega y monitores)"]
        R[API en Render<br/>Docker + HTTPS]
        S[(PostgreSQL en Supabase)]
        R --> S
    end

    Apps[Apps móviles] -- localhost / adb reverse --> L1
    Apps -- URL pública HTTPS --> R
```

La única diferencia entre entornos es la variable `DATABASE_URL`; el código y el esquema son los mismos.

## 3. Modelo entidad-relación

`restaurant_id` es texto sin llave foránea porque todavía no existe una tabla `restaurants` en el backend.

```mermaid
erDiagram
    users ||--o{ app_opens : "abre la app"
    users ||--o{ occupancy_events : "genera"
    users ||--o{ restaurant_views : "consulta"
    users ||--o{ saved_restaurants : "guarda"
    users ||--o| user_profiles : "tiene"
    users ||--o{ reviews : "escribe"
    users ||--o{ occupancy_reports : "reporta"

    users {
        int id PK
        string email UK
        string name
        string password_hash
        timestamptz created_at
    }

    app_opens {
        int id PK
        int user_id FK
        string meal_slot
        timestamptz timestamp
    }

    occupancy_events {
        int id PK
        int user_id FK
        string restaurant_id
        string event
        boolean has_data
        timestamp timestamp
    }

    restaurant_views {
        int id PK
        int user_id FK
        string restaurant_id
        timestamptz viewed_at
    }

    saved_restaurants {
        int user_id PK, FK
        string restaurant_id PK
        timestamptz saved_at
    }

    user_profiles {
        int user_id PK, FK
        string name
        json cuisines
        json dietary_restrictions
        string meal_frequency
        json meal_times
        string budget
        json priorities
        string disliked_foods
        timestamptz updated_at
    }

    reviews {
        int id PK
        string restaurant_id
        int user_id FK
        int taste
        int attention
        int price
        int options
        json dietary_options
        text comment
        timestamp created_at
    }

    occupancy_reports {
        int id PK
        string restaurant_id
        int user_id FK
        int level
        timestamp created_at
    }
```

### Tablas sin relación con usuarios (analítica anónima)

```mermaid
erDiagram
    zero_result_searches {
        int id PK
        string query
        timestamptz timestamp
    }

    onboarding_events {
        int id PK
        string session_id
        string event
        int step
        timestamptz timestamp
    }

    filter_usages {
        int id PK
        string filter
        string screen
        timestamptz timestamp
    }

    occupancy_checks {
        int id PK
        string restaurant_id
        string screen
        string action
        timestamptz timestamp
    }

    profile_edits {
        int id PK
        string install_id
        string field
        timestamptz timestamp
    }
```

## 4. Restricciones e índices

| Tabla | Restricción | Detalle |
|---|---|---|
| `users` | Único | `email` (índice único `ix_users_email`) |
| `reviews` | Único compuesto | `uq_review_user_restaurant` sobre `(user_id, restaurant_id)`: una reseña por usuario y restaurante |
| `saved_restaurants` | PK compuesta | `(user_id, restaurant_id)` |
| `user_profiles` | PK = FK | `user_id` → `users.id`, relación 1 a 1 |
| Tablas con `user_id` | Llave foránea | `user_id` → `users.id` |
| Casi todas | Índices | En `id`, `user_id`, `restaurant_id` y columnas de fecha usadas en consultas |

Las contraseñas se guardan como hash bcrypt (`$2b$12$...`); nunca en texto plano. Las 13 tablas tienen *row level security* activada (migración `0002`) sin políticas: solo el rol dueño, que es el que usa la API, puede leerlas.

## 5. Fechas y zonas horarias

| Tipo | Columnas | Comportamiento |
|---|---|---|
| `timestamptz` | `created_at`, `timestamp`, `viewed_at`, `saved_at`, `updated_at` en las tablas anteriores | Valor por defecto `now()` del servidor; se devuelve con zona UTC |
| `timestamp` (sin zona) | `occupancy_events.timestamp`, `reviews.created_at`, `occupancy_reports.created_at` | UTC puesto desde Python, para poder compararlas sin errores |

Cada conexión ejecuta `SET TIME ZONE 'UTC'`.

## 6. Esquema y datos: tres operaciones distintas

```mermaid
flowchart TD
    A[Base vacía] -->|alembic upgrade head| B[Esquema creado y versionado]
    B --> C{¿Importar datos antiguos?}
    C -- No --> D[Desarrollo limpio]
    C -- Sí --> E[scripts.import_sqlite campus_eats.db]
    E --> F{¿Alguna tabla tiene filas?}
    F -- Sí --> G[Se rechaza: no duplica ni borra]
    F -- No --> H[Importa en una transacción<br/>y compara fila por fila]
    H --> I{¿Discrepancias?}
    I -- Sí --> J[Rollback: no se guarda nada]
    I -- No --> K[Commit y ajuste de secuencias]
```

## 7. Migraciones

| Revisión | Contenido |
|---|---|
| `0001` | Esquema inicial: 13 tablas, llaves, restricciones e índices |
| `0002` | Activa *row level security* en las 13 tablas |

Comandos: `alembic upgrade head` aplica; `alembic current` muestra la versión; `alembic check` detecta diferencias entre los modelos y la base.
