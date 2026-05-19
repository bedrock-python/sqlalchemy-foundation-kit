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

### Nested Transactions (Savepoints)

SQLAlchemy supports nested transactions via savepoints:

```python
async with uow.transaction() as tx:
    # Outer transaction
    user = await tx.users.create(email="user@example.com")
    
    # Try nested operation with savepoint
    try:
        async with tx.session.begin_nested():
            # This might fail
            await tx.orders.create(user_id=user.id, total=-100)
    except Exception:
        # Nested transaction rolled back, outer continues
        pass
    
    # Outer transaction still succeeds
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

- **String keys** — Automatically hashed to integers: `"process_payments"`, `"user:123"`
- **Integer keys** — Used directly: `123456`, `user.id`

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

# Create metrics collector
metrics = PostgresMetrics(
    prefix="myapp",
    service_name="identity-service",
    labels={"environment": "production"},
)

# Pass to session manager
session_manager = create_async_session_manager(
    settings.postgres,
    metrics=metrics,
)
```

**Collected Metrics:**

| Metric | Type | Description |
|--------|------|-------------|
| `myapp_postgres_pool_size` | Gauge | Current pool size |
| `myapp_postgres_pool_checked_out` | Gauge | Connections currently in use |
| `myapp_postgres_pool_overflow` | Gauge | Overflow connections created |
| `myapp_postgres_checkout_duration_seconds` | Histogram | Time to acquire connection |
| `myapp_postgres_errors_total` | Counter | Database errors by type |
| `myapp_postgres_timeouts_total` | Counter | Connection timeout errors |

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
(myapp_postgres_pool_checked_out / myapp_postgres_pool_size) * 100

# P95 checkout latency
histogram_quantile(0.95, 
  rate(myapp_postgres_checkout_duration_seconds_bucket[5m]))

# Error rate
rate(myapp_postgres_errors_total[5m])
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

```python
# Check database connectivity
is_healthy = await session_manager.healthcheck()

if not is_healthy:
    logger.error("Database health check failed")

# With custom query
is_healthy = await session_manager.healthcheck(
    query="SELECT 1 FROM users LIMIT 1"
)
```

### Graceful Shutdown

```python
import signal
import asyncio

async def shutdown(session_manager: AsyncSessionManager):
    """Graceful shutdown handler."""
    logger.info("Shutting down database connections...")
    
    # Wait for in-flight requests to complete
    await session_manager.close(timeout=30.0)
    
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

Automatically retry on transient connection errors:

```python
from sqlalchemy_foundation_kit import (
    retry_async_connection,
    RetryConfig,
)

# Custom retry config
retry_config = RetryConfig(
    max_attempts=5,
    initial_delay=1.0,
    max_delay=30.0,
    exponential_base=2.0,
    jitter=True,
)

@retry_async_connection(config=retry_config)
async def fetch_user(session, user_id: UUID):
    """Retries on connection errors."""
    result = await session.execute(
        select(UserDB).where(UserDB.id == user_id)
    )
    return result.scalar_one_or_none()

# Use in transaction
async with session_manager.get_transaction() as session:
    user = await fetch_user(session, user_id)
```

### pgbouncer Compatibility

For pgbouncer transaction mode, disable prepared statements:

```python
from sqlalchemy_foundation_kit.contrib.settings import (
    BasePostgresConfig,
    QuerySettings,
)

config = BasePostgresConfig(
    connection=...,
    pool=PoolSettings(
        size=20,  # pgbouncer manages actual connections
        max_overflow=0,  # No overflow with pgbouncer
    ),
    query=QuerySettings(
        statement_cache_size=0,  # Required for pgbouncer
        prepared_statement_cache_size=0,  # Required for pgbouncer
    ),
    jit="off",  # Required for pgbouncer
)
```

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
