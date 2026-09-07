# Advanced Usage

This guide covers advanced features: Unit of Work patterns, observability (metrics and tracing), dependency injection, advisory locks, and connection management.

## Unit of Work (UoW)

The Unit of Work pattern ensures that all repository operations within a transaction either succeed together or fail together, maintaining data consistency.

### Basic UoW Usage

```python
from sqlalchemy_foundation_kit import (
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
)

# 1. Define transaction with repositories
class MyTransaction(AsyncSQLAlchemyUowTransaction):
    def __init__(self, session):
        super().__init__(session)
        self._users = None
        self._orders = None
    
    @property
    def users(self):
        """Lazy-loaded user repository."""
        if self._users is None:
            self._users = PostgresUserRepository(self.session)
        return self._users
    
    @property
    def orders(self):
        """Lazy-loaded order repository."""
        if self._orders is None:
            self._orders = PostgresOrderRepository(self.session)
        return self._orders

# 2. Create UoW
class MyUnitOfWork(AsyncSQLAlchemyUnitOfWork[MyTransaction]):
    def __init__(self, session_maker):
        super().__init__(
            session_maker,
            transaction_factory=MyTransaction,
            flush_before_commit=True,  # Flush before commit (default)
        )

# 3. Use in application layer
async with uow.transaction() as tx:
    user = await tx.users.create(email="user@example.com")
    order = await tx.orders.create(user_id=user.id, total=100.0)
    # Both operations committed together
    # Auto-rollback on exception
```

### Isolation Levels

Control transaction isolation for consistency vs. performance tradeoffs:

```python
from sqlalchemy_foundation_kit import IsolationLevel

# Default (READ COMMITTED) - good for most cases
async with uow.transaction() as tx:
    user = await tx.users.get_by_id(user_id)

# REPEATABLE READ - prevents non-repeatable reads
async with uow.transaction(isolation_level=IsolationLevel.REPEATABLE_READ) as tx:
    user = await tx.users.get_by_id(user_id)
    # Same user will always have the same data within this transaction

# SERIALIZABLE - strongest consistency guarantees
async with uow.transaction(isolation_level=IsolationLevel.SERIALIZABLE) as tx:
    user = await tx.users.get_by_id(user_id)
    balance = await tx.accounts.get_balance(user.account_id)
    # Full transactional isolation, may retry on conflicts

# String format also works
async with uow.transaction(isolation_level="READ COMMITTED") as tx:
    # ...
```

**Isolation Levels:**

- `READ_UNCOMMITTED` — Allows dirty reads (rarely used)
- `READ_COMMITTED` — Default, prevents dirty reads
- `REPEATABLE_READ` — Prevents non-repeatable reads, snapshot isolation
- `SERIALIZABLE` — Strongest guarantees, may have serialization failures

The level is set on the connection this block checks out, so it applies to this
transaction and leaves the engine alone. It has to be set before the transaction starts,
which means the block's transaction opens as the context manager is entered — including
in `query()`, which otherwise waits for the first statement. To set a level for every
session instead, pass `isolation_level=` to `AsyncSessionManager` or set
`QuerySettings.isolation_level`.

### Read-Only Queries

For read-only operations without transaction overhead:

```python
# Query context - no transaction management
async with uow.query() as qx:
    users = await qx.users.list_all(limit=100)
    # No commit/rollback, just queries

# With isolation level
async with uow.query(isolation_level=IsolationLevel.REPEATABLE_READ) as qx:
    users = await qx.users.list_all()
```

### Manual Transaction Control

For complex scenarios where you need explicit commit control:

```python
async with uow.managed_session() as (tx, session):
    try:
        user = await tx.users.create(email="user@example.com")
        
        # Conditional logic
        if should_create_profile:
            profile = await tx.profiles.create(user_id=user.id)
        
        # Manual commit
        await session.commit()
    except Exception:
        # Manual rollback
        await session.rollback()
        raise
```

### Savepoints (Partial Failure Inside a Transaction)

On PostgreSQL a single failed statement aborts the *whole* transaction: every later statement on
the connection fails until rollback — including the ones you would use to record which step failed.
A batch that processes independent items in one transaction therefore loses all of them to the
first bad one, and cannot even write down which one it was.

`tx.savepoint()` narrows that blast radius to a block. On exception the block's changes are rolled
back, the exception propagates so *you* decide what a failed item means, and the surrounding
transaction stays usable:

```python
async with uow.transaction() as tx:
    for event in await tx.outbox.list_pending():
        try:
            async with tx.savepoint():
                await handle(event)
                await tx.outbox.mark_processed(event.id)
        except Exception as exc:
            # Runs on a healthy transaction: only the savepoint was rolled back, not the batch
            await tx.outbox.mark_failed(event.id, reason=str(exc))
    # Processed events and failure records are committed together
```

`savepoint()` is available on every `AsyncSQLAlchemyUowTransaction` — no mixin required — and
yields nothing, so application code never touches SQLAlchemy. Use it inside `transaction()` or
`managed_session()`. Savepoints nest: a `savepoint()` inside another rolls back only the inner block.

If your use cases type their transaction as a `Protocol` rather than the concrete class, declare
the capability with `SupportsSavepoint`, the same way `SupportsAdvisoryLock` works:

```python
from typing import Protocol
from sqlalchemy_foundation_kit import SupportsSavepoint

class OutboxTransaction(SupportsSavepoint, Protocol):
    outbox: OutboxRepository

async def drain(tx: OutboxTransaction) -> None:
    for event in await tx.outbox.list_pending():
        async with tx.savepoint():
            ...
```

## Advisory Locks

PostgreSQL advisory locks prevent concurrent execution of critical sections:

```python
from sqlalchemy_foundation_kit import (
    PostgresAdvisoryLockMixin,
    try_advisory_xact_lock,
)

# Option 1: Mixin for transaction class
class MyTransaction(AsyncSQLAlchemyUowTransaction, PostgresAdvisoryLockMixin):
    # Inherits try_advisory_lock method
    pass

async with uow.transaction() as tx:
    # Try to acquire lock
    if await tx.try_advisory_lock("process_payments"):
        # Only one transaction can hold this lock
        await tx.process_payments()
    else:
        # Lock held by another transaction, skip
        logger.info("Payment processing already in progress")

# Option 2: Direct lock usage
async with session_manager.get_transaction() as session:
    if await try_advisory_xact_lock(session, "unique_job"):
        # Critical section
        await process_unique_job()
```

**Lock Keys:**

- **String keys** — Hashed to integers with BLAKE2b: `"process_payments"`, `"user:123"`.
  The hash is reproducible, so every replica of a service turns the same string into the
  same lock. The key changes between library versions only if this page says so.
- **Integer keys** — Used directly: `123456`, `user.id`. Values outside PostgreSQL's
  `bigint` range are wrapped into it.

**Lock Types:**

- **Transaction-scoped** (`pg_try_advisory_xact_lock`) — Released automatically at transaction end
- **Session-scoped** — Manual release required (not recommended)

**Use Cases:**

- Prevent duplicate background job execution
- Coordinate distributed locks across services
- Rate limiting per user/resource
- Ensure single-writer for critical operations

```python
# Example: Idempotent background job
class ProcessPaymentsUseCase:
    async def execute(self):
        async with self._uow.transaction() as tx:
            # Only one instance can process payments at a time
            if not await tx.try_advisory_lock("process_payments"):
                logger.info("Another instance is processing payments")
                return
            
            # Process pending payments
            pending = await tx.payments.list_pending()
            for payment in pending:
                await tx.payments.process(payment.id)
```

## Observability

### Prometheus Metrics

Track connection pool health and query performance:

```bash
pip install sqlalchemy-foundation-kit[metrics]
```

```python
from sqlalchemy_foundation_kit.contrib.metrics import PostgresMetrics

# Create metrics collector. `prefix` is the only argument; it is prepended with an
# underscore and must match ^[a-zA-Z_][a-zA-Z0-9_]*$.
metrics = PostgresMetrics(prefix="myapp")

# Pass to session manager
session_manager = create_async_session_manager(
    settings.postgres,
    metrics=metrics,
)
```

**Collected Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `myapp_postgres_db_pool_size` | Gauge | Current pool size |
| `myapp_postgres_db_pool_checked_out` | Gauge | Connections currently in use |
| `myapp_postgres_db_pool_overflow` | Gauge | Overflow connections created |
| `myapp_postgres_db_connection_checkout_wait_seconds` | Histogram | Time a caller **waited** for a connection |
| `myapp_postgres_db_connection_held_duration_seconds` | Histogram | Time a caller **held** a connection, checkout to checkin |
| `myapp_postgres_db_connection_checkout_duration_seconds` | Histogram | Deprecated alias of the held duration — see below |
| `myapp_postgres_db_connection_errors_total` | Counter | Database errors by type (`error_type` label) |
| `myapp_postgres_db_connection_timeouts_total` | Counter | Pool checkout timeouts, and `TimeoutError`s during execution |

Without a `prefix` the names are `postgres_db_pool_size` and so on.

**Wait or held — they are not the same number.** The wait is the time spent inside
`pool.connect()` before a connection is handed out: the queue wait, plus the pre-ping and
the connect handshake when the pool has to grow. It is the metric that predicts a pool
outage — it climbs while the pool saturates, and turns into
`connection_timeouts_total` when it crosses `pool_timeout`. The held duration is the time
between the `checkout` and `checkin` events, which is query duration seen from the pool: it
climbs when the database slows down, whether or not the pool is under any pressure. A
saturated pool moves both, and only the wait tells you which one caused the other.

**`connection_checkout_duration_seconds` is deprecated.** It has always measured the
*held* duration, despite the name. It is still published, unchanged, so existing dashboards
keep working, and it will be removed in a future release. Point dashboards at
`connection_held_duration_seconds` for the same numbers, or at
`connection_checkout_wait_seconds` if what you actually wanted was the wait.

The wait histogram and the pool-timeout half of the counter are not event listeners —
SQLAlchemy fires no event when a checkout is *requested* — so they come from the pool class
the session manager builds. They are populated on any engine created by
`AsyncSessionManager`, `AsyncSessionManagerBuilder` or `create_async_session_manager`. On
an engine you build yourself, wrap the pool class:

```python
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy_foundation_kit import resolve_pool_class
from sqlalchemy_foundation_kit.session.manager import attach_metrics, instrument_pool_class

metrics = PostgresMetrics(prefix="myapp")
engine = create_async_engine(
    url,
    poolclass=instrument_pool_class(resolve_pool_class("async_adapted_queue"), metrics),
)
attach_metrics(engine, metrics)
```

`attach_metrics` logs a warning if the engine's pool was not built this way, rather than
leaving you with a wait histogram that never moves.

**Expose metrics endpoint:**

```python
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response

@app.get("/metrics")
async def metrics_endpoint():
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
```

**Grafana Dashboard Example:**

```promql
# Pool utilization
(myapp_postgres_db_pool_checked_out / myapp_postgres_db_pool_size) * 100

# P95 wait for a connection -- the one to alert on
histogram_quantile(0.95,
  rate(myapp_postgres_db_connection_checkout_wait_seconds_bucket[5m]))

# Checkouts that gave up waiting
rate(myapp_postgres_db_connection_timeouts_total[5m])

# P95 time a connection was held -- query latency, seen from the pool
histogram_quantile(0.95,
  rate(myapp_postgres_db_connection_held_duration_seconds_bucket[5m]))

# Error rate
rate(myapp_postgres_db_connection_errors_total[5m])
```

### OpenTelemetry Tracing

Automatic distributed tracing for database operations:

```bash
pip install sqlalchemy-foundation-kit[telemetry]
```

```python
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
    OTLPSpanExporter,
)
from sqlalchemy_foundation_kit.contrib.telemetry import (
    instrument_sqlalchemy,
    instrument_asyncpg,
    TracedAsyncUnitOfWork,
)

# 1. Setup OpenTelemetry
provider = TracerProvider()

# Console exporter for development
provider.add_span_processor(
    BatchSpanProcessor(ConsoleSpanExporter())
)

# OTLP exporter for production (Jaeger, Tempo, etc.)
provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(endpoint="http://localhost:4317")
    )
)

trace.set_tracer_provider(provider)

# 2. Instrument SQLAlchemy
instrument_sqlalchemy(
    engine=engine,
    service_name="identity-service",
)

# 3. Instrument asyncpg (optional, more detailed)
instrument_asyncpg()

# 4. Use traced UoW
uow = TracedAsyncUnitOfWork(
    session_maker=session_maker,
    transaction_factory=MyTransaction,
    service_name="identity-service",
)

# All operations automatically traced
async with uow.transaction() as tx:
    user = await tx.users.create(email="user@example.com")
    # Creates span: uow.transaction
    #   with attributes: db.operation=transaction
```

**Trace Attributes:**

- `db.operation` — Operation type (`transaction`, `query`, `managed_session`)
- `db.isolation_level` — Transaction isolation level
- `db.statement` — SQL statement (from SQLAlchemy instrumentation)
- `db.system` — Database system (`postgresql`)

**Manual Spans:**

```python
from opentelemetry import trace

tracer = trace.get_tracer(__name__)

async def create_user_with_profile(email: str):
    with tracer.start_as_current_span("create_user_with_profile") as span:
        span.set_attribute("user.email", email)
        
        async with uow.transaction() as tx:
            user = await tx.users.create(email=email)
            profile = await tx.profiles.create(user_id=user.id)
            
            span.set_attribute("user.id", str(user.id))
        
        return user
```

## Dependency Injection

### Dishka (Recommended)

```bash
pip install sqlalchemy-foundation-kit[dishka]
```

```python
from dishka import make_async_container, Scope
from sqlalchemy_foundation_kit.contrib.di import (
    AsyncDatabaseProvider,
    AsyncUnitOfWorkProvider,
    PrometheusPostgresMetricsProvider,
)

# Define your providers
from dishka import Provider, provide

class SettingsProvider(Provider):
    scope = Scope.APP
    
    @provide
    def get_settings(self) -> Settings:
        return Settings()

class UseCaseProvider(Provider):
    scope = Scope.REQUEST
    
    @provide
    def get_create_user_use_case(
        self,
        uow: MyUnitOfWork,
    ) -> CreateUserUseCase:
        return CreateUserUseCase(uow)

# Create container
container = make_async_container(
    # Settings
    SettingsProvider(),
    
    # Database infrastructure
    AsyncDatabaseProvider(),  # Provides AsyncSessionManager, async_sessionmaker
    AsyncUnitOfWorkProvider(),  # Provides AsyncUnitOfWork
    PrometheusPostgresMetricsProvider(),  # Provides PostgresMetrics
    
    # Application layer
    UseCaseProvider(),
)

# Use in FastAPI
from dishka.integrations.fastapi import setup_dishka

app = FastAPI()
setup_dishka(container, app)

@app.post("/users")
async def create_user(
    use_case: FromDishka[CreateUserUseCase],
    body: CreateUserRequest,
):
    user = await use_case.execute(body.email, body.username)
    return {"user_id": str(user.id)}
```

### dependency-injector

```bash
pip install sqlalchemy-foundation-kit[dependency-injector]
```

```python
from dependency_injector import containers, providers
from sqlalchemy_foundation_kit.contrib.dependency_injector import (
    DatabaseContainer,
    PrometheusMetricsContainer,
)

class AppContainer(containers.DeclarativeContainer):
    # Configuration
    config = providers.Singleton(Settings)
    
    # Metrics
    metrics = providers.Container(
        PrometheusMetricsContainer,
        postgres_settings=config.provided.postgres,
        default_prefix="myapp",
    )
    
    # Database
    database = providers.Container(
        DatabaseContainer,
        postgres_config=config.provided.postgres,
        metrics=metrics.postgres_metrics,
    )
    
    # Use cases
    create_user_use_case = providers.Factory(
        CreateUserUseCase,
        uow=database.uow,
    )

# Initialize
container = AppContainer()
await container.init_resources()

# Use
use_case = container.create_user_use_case()
user = await use_case.execute("user@example.com", "username")

# Cleanup
await container.shutdown_resources()
```

## Connection Management

### Health Checks

There is no `healthcheck()` method — the library ships the query and leaves the policy to
you:

```python
from sqlalchemy import text
from sqlalchemy_foundation_kit import DEFAULT_HEALTHCHECK_QUERY

async def is_healthy(session_manager: AsyncSessionManager) -> bool:
    """Check database connectivity."""
    try:
        async with session_manager.get_session() as session:
            await session.execute(text(DEFAULT_HEALTHCHECK_QUERY))
    except Exception:
        logger.exception("Database health check failed")
        return False
    return True
```

The DI providers run exactly this at startup — see `AsyncDatabaseProvider` and
`DatabaseContainer`, both of which take `healthcheck_query=None` to skip it.

### Graceful Shutdown

`aclose()` disposes the engine under `asyncio.shield`, capped by the manager's
`dispose_timeout` (30 seconds by default). It is idempotent, and logs a warning rather
than raising if the timeout expires.

```python
import signal
import asyncio

# The timeout belongs to the manager, not to the call that closes it
session_manager = create_async_session_manager(settings.postgres, dispose_timeout=30.0)

async def shutdown(session_manager: AsyncSessionManager):
    """Graceful shutdown handler."""
    logger.info("Shutting down database connections...")
    
    # Wait for in-flight requests to complete
    await session_manager.aclose()
    
    logger.info("Database connections closed")

# Register signal handlers
loop = asyncio.get_event_loop()

for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(
        sig,
        lambda: asyncio.create_task(shutdown(session_manager))
    )

# Run application
await run_app()
```

### Connection Retry

`retry_async_connection` is a coroutine function, not a decorator, and it retries a
callable that establishes or tests a connection — the startup wait, not every query. It
re-raises the last exception when the attempts run out:

```python
from sqlalchemy import text
from sqlalchemy_foundation_kit import (
    DEFAULT_HEALTHCHECK_QUERY,
    RetryConfig,
    retry_async_connection,
)

# Custom retry config: attempt N sleeps retry_delay * 2 ** N, capped at max_backoff_delay
retry_config = RetryConfig(
    max_retries=5,
    retry_delay=1.0,
    max_backoff_delay=30.0,
)

async def wait_for_database(session_manager: AsyncSessionManager) -> None:
    async def connect() -> None:
        async with session_manager.get_session() as session:
            await session.execute(text(DEFAULT_HEALTHCHECK_QUERY))

    await retry_async_connection(
        connect_func=connect,
        service_name="PostgreSQL",
        config=retry_config,
    )

await wait_for_database(session_manager)
```

### PgBouncer Compatibility

`create_async_session_manager` is safe behind PgBouncer in transaction mode as it stands:
both statement caches default to 0 and the connection class is `AsyncCConnection`, whose
statement names are unique per connection (both for PgBouncer before 1.22); `jit` is not
sent unless you set it; and `db_schema` is applied with `SET LOCAL` at the start of every
transaction rather than as a startup parameter. The one thing left to size is the pool:
PgBouncer owns the server connections, so `size` is how many client connections this
process may hold open.

```python
from sqlalchemy_foundation_kit.contrib.settings import (
    BasePostgresConfig,
    ConnectionSettings,
    PoolSettings,
)

config = BasePostgresConfig(
    connection=ConnectionSettings(host="pgbouncer", port=6432, ...),
    pool=PoolSettings(size=20, max_overflow=0),
    application_name="my-service",
    db_schema="app",
)
```

Do not set `jit="off"` for PgBouncer. It travels as a startup parameter, which PgBouncer in
transaction mode rejects (`unsupported startup parameter: jit`), so every connection fails.
The measurements and the reasoning are in [Configuration → PgBouncer](configuration.md#pgbouncer).

## Custom Types

### PydanticJSONB

Store and retrieve Pydantic models as JSONB:

```python
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import PydanticJSONB, BaseTable

class UserPreferences(BaseModel):
    theme: str
    language: str
    notifications: bool

class UserDB(BaseTable):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    preferences: Mapped[UserPreferences] = mapped_column(
        PydanticJSONB(UserPreferences)
    )

# Usage
user = UserDB(
    preferences=UserPreferences(
        theme="dark",
        language="en",
        notifications=True,
    )
)

# Automatically validated on retrieval
prefs = user.preferences  # UserPreferences instance
print(prefs.theme)  # "dark"
```

### UnConstrainedEnum

Store enums without database constraints for flexibility:

```python
from enum import Enum
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_foundation_kit import UnConstrainedEnum, BaseTable

class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"

class UserDB(BaseTable):
    __tablename__ = "users"
    
    id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[UserRole] = mapped_column(
        UnConstrainedEnum(UserRole)
    )

# Add new enum values without migration
class UserRole(str, Enum):
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"
    MODERATOR = "moderator"  # New value
```

## Next Steps

- **[API Reference](../reference/index.md)** — Complete API documentation
- **[Configuration](configuration.md)** — Detailed configuration options
- **[Quick Start](quickstart.md)** — Working examples
