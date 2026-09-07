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
        jit=None,
        metrics_enabled=True,
    )

settings = Settings()
```

### Environment Variables

`BasePostgresConfig` declares no `model_config` of its own, so it reads no prefix and no
delimiter by itself. Environment variables reach it through the `BaseSettings` that holds
it, which is where `env_nested_delimiter` is set:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_nested_delimiter="__")

    postgres: BasePostgresConfig
```

Every level of nesting is then one `__`, the field name included — `postgres` is a field
like any other, so `postgres.connection.host` is `POSTGRES__CONNECTION__HOST`:

```bash
# Connection settings
POSTGRES__CONNECTION__HOST=db.example.com
POSTGRES__CONNECTION__PORT=5432
POSTGRES__CONNECTION__USER=postgres
POSTGRES__CONNECTION__PASSWORD=secret123
POSTGRES__CONNECTION__DATABASE=mydb

# Pool settings
POSTGRES__POOL__SIZE=20
POSTGRES__POOL__MAX_OVERFLOW=30
POSTGRES__POOL__TIMEOUT=45.0
POSTGRES__POOL__PRE_PING=true
POSTGRES__POOL__RECYCLE=1800

# Query settings
POSTGRES__QUERY__ECHO=false
POSTGRES__QUERY__STATEMENT_CACHE_SIZE=0
POSTGRES__QUERY__ISOLATION_LEVEL="READ COMMITTED"

# Top-level settings
POSTGRES__APPLICATION_NAME=my-service
POSTGRES__DB_SCHEMA=public
POSTGRES__USE_ORJSON_SERIALIZATION=true
POSTGRES__JIT=off   # a startup parameter: direct connections only, see PgBouncer below
POSTGRES__METRICS_ENABLED=true
```

`BasePostgresMigrationsConfig` is exactly this settings class, ready made: it holds a
`postgres: BasePostgresConfig` with `env_nested_delimiter="__"` and `extra="ignore"`
already set, and reads the same names.

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

Now use `MY_APP_POSTGRES__CONNECTION__HOST` instead of `POSTGRES__CONNECTION__HOST`.

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
| `db_schema` | `str \| None` | `None` | `search_path` applied to every transaction with `SET LOCAL` — a schema, or a comma-separated list |
| `use_orjson_serialization` | `bool` | `True` | Use `orjson` for JSON serialization (requires `[orjson]` extra) |
| `jit` | `"off" \| "on" \| None` | `None` | PostgreSQL JIT setting, sent as a startup parameter only when set |
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

The value is a `search_path`, so `"tenant_123, public"` is valid too. It is applied at the
start of every transaction with `SET LOCAL` semantics — `set_config('search_path', …, true)`
as the first statement after `BEGIN` — which is the one scope that survives a
transaction-mode pooler. Every `transaction()`, `query()`, `managed_session()`,
`get_session()`, `get_transaction()` and raw `engine.connect()` block sees it, including
the transaction that follows a `commit()` in the same session. Two things it is not: a
startup parameter, which PgBouncer rejects or drops (see [PgBouncer](#pgbouncer)), and a
session-level `SET`, which leaks between clients through a pooler. A statement run with
`isolation_level="AUTOCOMMIT"` begins no transaction and therefore runs with the server's
default `search_path`.

If you would rather not pay one round-trip per transaction, set it on the server instead —
`ALTER ROLE app_user SET search_path = tenant_123` or `ALTER DATABASE mydb SET search_path =
tenant_123` — and leave `db_schema` unset; or qualify the schema in your metadata
(`__table_args__ = {"schema": "tenant_123"}`) and need no `search_path` at all. Outside
`create_async_session_manager` the same mechanism is `AsyncSessionManager(...,
search_path="tenant_123")` or `AsyncSessionManagerBuilder(url).with_search_path("tenant_123")`.

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

`jit` is `None` by default: nothing is sent and PostgreSQL's own setting applies (`on`
since PostgreSQL 12). Set `"off"` or `"on"` only to override the server for this
application, and know that the value travels as a startup parameter — fine on a direct
connection, rejected by PgBouncer in transaction mode unless it is listed in
`track_extra_parameters` (see [PgBouncer](#pgbouncer)). Behind a pooler, set it on the
server instead: `ALTER ROLE app_user SET jit = off`.

```python
# Direct PostgreSQL connection: override the server setting for this application
BasePostgresConfig(
    jit="off",
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
    jit: str | None = None
    metrics_enabled: bool = False
    
    def to_dsn(self, driver: str | None = "asyncpg", mask_password: bool = False) -> str:
        conn = self.connection
        password = "**********" if mask_password else conn.password.get_secret_value()
        scheme = f"postgresql+{driver}" if driver else "postgresql"
        return f"{scheme}://{conn.user}:{password}@{conn.host}:{conn.port}/{conn.database}"
```

## PgBouncer

Measured on PostgreSQL 17 and PgBouncer 1.25 in transaction mode, PgBouncer at its
defaults unless the row says otherwise: twenty clients, twenty distinct statements each,
run twice, so every cache fills. The scripts are on
[issue #23](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/23).

| Client | Through | Result |
|---|---|---|
| plain SQLAlchemy + asyncpg, driver defaults | PostgreSQL directly | 800 of 800 ok |
| plain SQLAlchemy + asyncpg, driver defaults | PgBouncer, defaults (`max_prepared_statements=200`) | 800 of 800 ok |
| plain SQLAlchemy + asyncpg, driver defaults | PgBouncer, `max_prepared_statements=0` (the default before 1.22) | 485 of 800 ok; 315 × `prepared statement "__asyncpg_stmt_…" does not exist` |
| `create_async_session_manager(config)`, 0.2.1 | PgBouncer, defaults | 0 of 800: every connection refused with `unsupported startup parameter: jit` |
| `create_async_session_manager(config)`, 0.2.1 | PgBouncer, `ignore_startup_parameters=jit,search_path` | 800 of 800 ok — and `SHOW jit` is `on`, `SHOW search_path` is `"$user", public`: both parameters silently dropped |
| `create_async_session_manager(config)`, current | PgBouncer, defaults | 800 of 800 ok; `SHOW search_path` is the configured `db_schema` |

Three things follow, and the library is built around each.

**Startup parameters do not pass through.** asyncpg's `server_settings` are parameters of
the PostgreSQL startup packet. PgBouncer forwards only the ones it tracks —
`client_encoding`, `datestyle`, `timezone`, `standard_conforming_strings`,
`application_name`, plus whatever you list in `track_extra_parameters` (1.18+) — and
refuses the connection on any other. `ignore_startup_parameters` makes the connection
succeed by throwing the parameter away, which is worse: a `search_path` the library
accepted and the database never saw. So `create_async_session_manager` sends
`application_name` and nothing else by default; `jit` goes only when you set it, and
`db_schema` never goes as a startup parameter.

**Session state does not survive a transaction.** In transaction mode a client owns a
server connection from `BEGIN` to `COMMIT` and not a moment longer. A plain `SET` outside
a transaction lands on whichever server connection was free and is visible to the next
client handed that connection — the last row of the lab: client A ran
`SET search_path TO leaked`, client B read `search_path = 'leaked'`. The only per-connection
state that behaves is state scoped to the transaction (`SET LOCAL`) or set on the server
for the role or database. That is why `db_schema` is applied as `SET LOCAL search_path` at
the start of every transaction, and why the alternatives are `ALTER ROLE … SET`,
`ALTER DATABASE … SET`, `track_extra_parameters`, or schema-qualified metadata — never a
`SET` in a `connect` listener.

**Prepared statements are fine on a current PgBouncer, and still not on an old one.**
Since 1.22 PgBouncer tracks protocol-level prepared statements itself
(`max_prepared_statements=200` by default), so the driver's default statement cache runs
clean. Before 1.22, or with `max_prepared_statements=0`, a cached statement name is unknown
to the server connection the next transaction lands on and the classic failure comes back.
`QuerySettings` defaults both caches to 0 and `create_async_session_manager` uses
`AsyncCConnection`, whose statement names are unique per connection, so the library is
safe on either; on 1.22+ you may raise the caches to win the round-trip back.

```python
# Behind PgBouncer in transaction mode this is all it takes
config = BasePostgresConfig(
    connection=ConnectionSettings(host="pgbouncer", port=6432, ...),
    application_name="my-service",
    db_schema="app",   # SET LOCAL at the start of every transaction: arrives
    # jit stays None   # nothing sent: the connection is accepted
)
manager = create_async_session_manager(config)
```

What not to do: `jit="off"` "for pgbouncer" (it is the one setting that makes the
connection impossible), `extra_server_settings={"search_path": ...}` (rejected, or dropped),
and a `SET search_path` in an `on_engine_created` connect listener (leaks between clients).

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

### 5. Behind PgBouncer, Send Nothing It Will Not Carry

The defaults already do the right thing — statement caches at 0, `jit` unset, `db_schema`
applied per transaction. Do not put `jit`, `search_path` or any other untracked parameter
into `extra_server_settings`; see [PgBouncer](#pgbouncer).

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
