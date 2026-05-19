# Configuration

`sqlalchemy-foundation-kit` provides flexible configuration options through protocols and optional Pydantic-based settings.

## Configuration Approaches

You have two options for configuring the library:

1. **`contrib.settings`** — Pydantic-based configuration (requires `[settings]` extra)
2. **Protocol-based** — Implement `PostgresSettingsProtocol` directly

## Using `contrib.settings` (Recommended)

Install with settings support:

```bash
pip install sqlalchemy-foundation-kit[settings]
```

### Basic Configuration

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings
from sqlalchemy_foundation_kit.contrib.settings import (
    BasePostgresConfig,
    ConnectionSettings,
    PoolSettings,
    QuerySettings,
)

class Settings(BaseSettings):
    postgres: BasePostgresConfig = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="postgres",
            password=SecretStr("secret"),
            database="mydb",
        ),
        pool=PoolSettings(
            size=10,
            max_overflow=20,
            timeout=30.0,
            pre_ping=True,
            recycle=3600,
        ),
        query=QuerySettings(
            echo=False,
            statement_cache_size=0,
            prepared_statement_cache_size=0,
            isolation_level="READ COMMITTED",
        ),
        application_name="my-service",
        db_schema=None,
        use_orjson_serialization=True,
        jit="off",
        metrics_enabled=True,
    )

settings = Settings()
```

### Environment Variables

`BasePostgresConfig` inherits from `pydantic_settings.BaseSettings`, so it automatically loads from environment variables:

```bash
# Connection settings
POSTGRES_CONNECTION__HOST=db.example.com
POSTGRES_CONNECTION__PORT=5432
POSTGRES_CONNECTION__USER=postgres
POSTGRES_CONNECTION__PASSWORD=secret123
POSTGRES_CONNECTION__DATABASE=mydb

# Pool settings
POSTGRES_POOL__SIZE=20
POSTGRES_POOL__MAX_OVERFLOW=30
POSTGRES_POOL__TIMEOUT=45.0
POSTGRES_POOL__PRE_PING=true
POSTGRES_POOL__RECYCLE=1800

# Query settings
POSTGRES_QUERY__ECHO=false
POSTGRES_QUERY__STATEMENT_CACHE_SIZE=0
POSTGRES_QUERY__ISOLATION_LEVEL="READ COMMITTED"

# Top-level settings
POSTGRES_APPLICATION_NAME=my-service
POSTGRES_DB_SCHEMA=public
POSTGRES_USE_ORJSON_SERIALIZATION=true
POSTGRES_JIT=off
POSTGRES_METRICS_ENABLED=true
```

**Custom prefix:**

```python
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MY_APP_",
        env_nested_delimiter="__",
    )
    
    postgres: BasePostgresConfig
```

Now use `MY_APP_POSTGRES_CONNECTION__HOST` instead of `POSTGRES_CONNECTION__HOST`.

### DSN Generation

```python
# Generate DSN for asyncpg
dsn = settings.postgres.to_dsn()
# postgresql+asyncpg://postgres:secret@localhost:5432/mydb

# Generate DSN without driver
dsn = settings.postgres.to_dsn(driver=None)
# postgresql://postgres:secret@localhost:5432/mydb

# Generate DSN with masked password (for logging)
dsn = settings.postgres.to_dsn(mask_password=True)
# postgresql+asyncpg://postgres:**********@localhost:5432/mydb
```

## Configuration Options

### Connection Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `host` | `str` | `"localhost"` | PostgreSQL server hostname or IP address |
| `port` | `int` | `5432` | PostgreSQL server port (1-65535) |
| `user` | `str` | `"postgres"` | PostgreSQL username |
| `password` | `SecretStr` | **required** | PostgreSQL password (auto-masked in logs) |
| `database` | `str` | **required** | Database name |

**Example:**

```python
ConnectionSettings(
    host="db.prod.example.com",
    port=5432,
    user="app_user",
    password=SecretStr("$ecr3t!"),
    database="production_db",
)
```

### Pool Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `kind` | `PoolClassStr` | `"async_adapted_queue"` | Pool implementation (`async_adapted_queue`, `static`, `null`) |
| `size` | `int` | `10` | Number of connections in the pool (minimum 1) |
| `max_overflow` | `int` | `20` | Additional connections when pool is exhausted (0 or more) |
| `pre_ping` | `bool` | `True` | Check connection health before use (recommended) |
| `recycle` | `int` | `3600` | Recycle connections after N seconds (-1 = never) |
| `timeout` | `float` | `30.0` | Seconds to wait for connection before raising error |

**Pool Types:**

- **`async_adapted_queue`** (default) — Standard async queue-based pool, recommended for most use cases
- **`static`** — Fixed-size pool with no overflow (`max_overflow` must be 0)
- **`null`** — No pooling, creates new connection for each request (not recommended for production)

**Example:**

```python
# Development: small pool with quick recycling
PoolSettings(
    size=5,
    max_overflow=10,
    pre_ping=True,
    recycle=600,  # 10 minutes
    timeout=10.0,
)

# Production: large pool with longer recycling
PoolSettings(
    size=20,
    max_overflow=30,
    pre_ping=True,
    recycle=3600,  # 1 hour
    timeout=30.0,
)

# High-throughput: static pool (no overflow)
PoolSettings(
    kind="static",
    size=50,
    max_overflow=0,  # Required for static pool
    pre_ping=True,
    recycle=1800,
    timeout=45.0,
)
```

**Validation:**

The library validates pool settings:

```python
# ❌ This raises ValueError
PoolSettings(
    kind="static",
    size=10,
    max_overflow=20,  # ❌ max_overflow must be 0 for static pool
)

# ✅ Correct
PoolSettings(
    kind="static",
    size=10,
    max_overflow=0,  # ✅ Valid
)
```

### Query Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `echo` | `bool` | `False` | Log all SQL statements (useful for debugging) |
| `statement_cache_size` | `int` | `0` | SQLAlchemy statement cache size (0 = no cache) |
| `prepared_statement_cache_size` | `int` | `0` | Prepared statement cache size (0 = no cache) |
| `isolation_level` | `str \| None` | `None` | Default transaction isolation level |

**Isolation Levels:**

- `"READ UNCOMMITTED"` — Lowest isolation, allows dirty reads
- `"READ COMMITTED"` — Default PostgreSQL level, prevents dirty reads
- `"REPEATABLE READ"` — Prevents non-repeatable reads
- `"SERIALIZABLE"` — Highest isolation, full transactional consistency

**Example:**

```python
# Development: verbose logging
QuerySettings(
    echo=True,  # Log all SQL
    statement_cache_size=0,  # Disable caching for debugging
    isolation_level=None,  # Use database default
)

# Production: optimized for performance
QuerySettings(
    echo=False,  # No SQL logging
    statement_cache_size=500,  # Cache common queries
    prepared_statement_cache_size=500,
    isolation_level="READ COMMITTED",
)

# High-consistency workload
QuerySettings(
    echo=False,
    statement_cache_size=0,  # Disable for pgbouncer transaction mode
    prepared_statement_cache_size=0,
    isolation_level="SERIALIZABLE",  # Strongest guarantees
)
```

### Top-Level Settings

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `application_name` | `str` | **required** | Application identifier in PostgreSQL logs |
| `db_schema` | `str \| None` | `None` | Default PostgreSQL schema name |
| `use_orjson_serialization` | `bool` | `True` | Use `orjson` for JSON serialization (requires `[orjson]` extra) |
| `jit` | `"off" \| "on" \| None` | `"off"` | PostgreSQL JIT compilation setting |
| `metrics_enabled` | `bool` | `False` | Enable Prometheus metrics (requires `[metrics]` extra) |

**Application Name:**

The `application_name` appears in PostgreSQL logs and monitoring tools, helping identify which service is issuing queries:

```python
BasePostgresConfig(
    application_name="identity-service",
    # ...
)
```

PostgreSQL `pg_stat_activity` will show:

```sql
SELECT application_name, query FROM pg_stat_activity;
-- application_name | query
-- identity-service | SELECT * FROM users WHERE id = $1
```

**Schema:**

```python
BasePostgresConfig(
    db_schema="tenant_123",
    # ...
)
```

Sets the default `search_path` for all connections.

**orjson Serialization:**

Install with `[orjson]` for faster JSON serialization:

```bash
pip install sqlalchemy-foundation-kit[orjson]
```

```python
BasePostgresConfig(
    use_orjson_serialization=True,
    # ...
)
```

Automatically used by `PydanticJSONB` type for better performance.

**JIT (Just-In-Time Compilation):**

PostgreSQL 11+ includes JIT compilation for complex queries. Disable when using pgbouncer in transaction mode:

```python
# pgbouncer transaction mode
BasePostgresConfig(
    jit="off",  # Required for pgbouncer
    # ...
)

# Direct PostgreSQL connection
BasePostgresConfig(
    jit="on",  # Can improve performance for complex queries
    # ...
)
```

## Protocol-Based Configuration

If you don't want `pydantic-settings`, implement `PostgresSettingsProtocol`:

```python
from dataclasses import dataclass
from pydantic import SecretStr
from sqlalchemy_foundation_kit import (
    PostgresSettingsProtocol,
    ConnectionSettingsProtocol,
    PoolSettingsProtocol,
    QuerySettingsProtocol,
)

@dataclass
class MyConnectionSettings:
    host: str = "localhost"
    port: int = 5432
    user: str = "postgres"
    password: SecretStr = SecretStr("secret")
    database: str = "mydb"

@dataclass
class MyPoolSettings:
    kind: str = "async_adapted_queue"
    size: int = 10
    max_overflow: int = 20
    pre_ping: bool = True
    recycle: int = 3600
    timeout: float = 30.0

@dataclass
class MyQuerySettings:
    echo: bool = False
    statement_cache_size: int = 0
    prepared_statement_cache_size: int = 0
    isolation_level: str | None = None

@dataclass
class MyPostgresConfig:
    connection: ConnectionSettingsProtocol
    pool: PoolSettingsProtocol
    query: QuerySettingsProtocol
    application_name: str = "my-service"
    db_schema: str | None = None
    use_orjson_serialization: bool = True
    jit: str | None = "off"
    metrics_enabled: bool = False
    
    def to_dsn(self, driver: str | None = "asyncpg", mask_password: bool = False) -> str:
        conn = self.connection
        password = "**********" if mask_password else conn.password.get_secret_value()
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        return f"{scheme}://{conn.user}:{password}@{conn.host}:{conn.port}/{conn.database}"
```

## Configuration Best Practices

### 1. Use Environment Variables

```python
# ✅ Load from environment
settings = Settings()  # Reads from env vars

# ❌ Hardcode secrets
settings = Settings(
    postgres=BasePostgresConfig(
        connection=ConnectionSettings(
            password=SecretStr("hardcoded-secret")  # ❌ Bad
        )
    )
)
```

### 2. Separate Configs by Environment

```python
# config/development.py
POSTGRES_POOL__SIZE=5
POSTGRES_POOL__MAX_OVERFLOW=10
POSTGRES_QUERY__ECHO=true

# config/production.py
POSTGRES_POOL__SIZE=20
POSTGRES_POOL__MAX_OVERFLOW=30
POSTGRES_QUERY__ECHO=false
```

### 3. Use Masked DSN in Logs

```python
# ✅ Mask password
logger.info(f"Connecting to: {settings.postgres.to_dsn(mask_password=True)}")
# Connecting to: postgresql+asyncpg://user:**********@localhost:5432/db

# ❌ Expose password
logger.info(f"Connecting to: {settings.postgres.to_dsn()}")
# Connecting to: postgresql+asyncpg://user:secret123@localhost:5432/db
```

### 4. Adjust Pool Size for Workload

```python
# High-concurrency API
PoolSettings(size=50, max_overflow=50)

# Background workers
PoolSettings(size=5, max_overflow=10)

# Batch processing
PoolSettings(size=2, max_overflow=0)
```

### 5. Disable Caching for pgbouncer

```python
# pgbouncer transaction mode
QuerySettings(
    statement_cache_size=0,  # Required
    prepared_statement_cache_size=0,  # Required
)
```

### 6. Enable Metrics in Production

```python
BasePostgresConfig(
    metrics_enabled=True,  # Track pool health
    # ...
)
```

## Next Steps

- **[Advanced Usage](advanced.md)** — Unit of Work, metrics, telemetry
- **[Quick Start](quickstart.md)** — Complete working example
- **[API Reference](../reference/index.md)** — Protocol definitions
