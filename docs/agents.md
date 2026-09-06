# sqlalchemy-foundation-kit for AI agents

> One page holding everything a coding assistant needs to wire and drive
> sqlalchemy-foundation-kit correctly, plus a map of where the rest of the documentation
> keeps the details it leaves out. Give an agent this page rather than the whole site.

| | |
|---|---|
| Package | `sqlalchemy-foundation-kit` on PyPI, import root `sqlalchemy_foundation_kit` |
| Requires | Python 3.11+, SQLAlchemy 2 (`>=2.0.35,<3`), Pydantic 2 (`>=2.5,<3`), PostgreSQL, and `asyncpg` — the import fails without it, see rule 1 |
| Install | `pip install sqlalchemy-foundation-kit asyncpg` · extras: `settings`, `metrics`, `orjson`, `dishka`, `dependency-injector`, `telemetry`, `all` |
| Async | the whole library. `AsyncEngine`, `AsyncSession`, `asyncpg` |
| Sync | none. There is no sync mirror and no sync entry point |
| Version | 0.2.0 — everything below was read from the source at that version |
| Source | <https://github.com/bedrock-python/sqlalchemy-foundation-kit> |

## How to read this page

Every page of this site is also served as raw Markdown at its own URL with `.md` in place
of the trailing slash — this page is `/agents.md`, the configuration guide is
`/guide/configuration.md` — so anything the map below points at can be fetched as plain
text rather than scraped out of HTML. The **Copy page** control at the top of a page does
the same thing for a human with a chat window open. The one exception is the API
reference: its Markdown is a list of instructions to a docstring renderer rather than the
API, so it carries neither the control nor a `.md` twin — read it as HTML, or read the
docstrings in the source.

Top to bottom before writing code. [Rules that hold or break the code](#rules-that-hold-or-break-the-code)
is the section correctness lives in, and it is followed by the short list of things that
are [broken at 0.2.0](#broken-at-020) — call one of those and the process raises, not the
database. Every name used below is in the public API; if you need something not listed
here, fetch the page the [documentation map](#documentation-map) points at rather than
guessing a method that sounds plausible.

## Scope

**It does** give an async PostgreSQL service the plumbing it would otherwise write for
itself: an engine and session factory with pooling, pgbouncer-safe connection settings
and pool metrics (`AsyncSessionManager`); a Unit of Work that owns one session per
transaction and commits or rolls it back for you (`AsyncSQLAlchemyUnitOfWork`); savepoints
and transaction-scoped advisory locks on that session; a declarative `Base` with a naming
convention, timestamp columns and a Pydantic-validated JSONB type; and optional
integrations for pydantic-settings, Prometheus, OpenTelemetry, dishka and
dependency-injector.

**It does not** give you repositories — you write those; the library only hands your
repository a session. It does not run migrations (that is Alembic's job; `load_orm_metadata`
is the only hook it offers), does not generate queries, does not retry a failed
transaction, does not pool anything itself beyond configuring SQLAlchemy's pools, and
supports no database other than PostgreSQL over asyncpg.

## Mental model

Five nouns, in the order a request passes through them.

* **`AsyncSessionManager`** owns the `AsyncEngine` and one `async_sessionmaker`. One per
  process, built at startup, closed with `await manager.aclose()` at shutdown. Everything
  downstream reads `manager.session_maker`.
* **The unit of work** — `AsyncSQLAlchemyUnitOfWork(session_maker, transaction_factory)` —
  is stateless. It holds the factory, not a session. Sharing one across the whole
  application is correct and intended.
* **A context manager on it opens exactly one session** and closes it on exit.
  `transaction()` commits on success and rolls back on exception; `managed_session()`
  hands you the session and commits nothing; `query()` starts no transaction of its own
  and throws away anything you write.
* **The transaction object** is what the context manager yields: your subclass of
  `AsyncSQLAlchemyUowTransaction`, constructed with that session, exposing your
  repositories as properties. `tx.session` is the `AsyncSession` underneath;
  `tx.savepoint()` is a nested block whose failure does not poison the surrounding
  transaction.
* **Your repositories** take that session, execute statements and `flush()`. They never
  commit — the commit belongs to the use case, at the unit-of-work boundary.

The session is the unit of concurrency as well as the unit of transaction: one session is
one connection, and one connection does one thing at a time. Everything above the session
is shareable; the session and everything holding it are not. See rules 6 and 7.

## Wiring

```python
import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from sqlalchemy_foundation_kit import (
    AsyncSessionManager,
    AsyncSQLAlchemyUnitOfWork,
    AsyncSQLAlchemyUowTransaction,
    BaseTable,
    DatetimeColumnsMixin,
)


class UserDB(BaseTable, DatetimeColumnsMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, email: str) -> UserDB:
        user = UserDB(email=email)
        self._session.add(user)
        await self._session.flush()          # flush, never commit
        return user


class Transaction(AsyncSQLAlchemyUowTransaction):
    @property
    def users(self) -> UserRepository:
        return UserRepository(self.session)


async def main() -> None:
    manager = AsyncSessionManager(
        "postgresql+asyncpg://user:pass@localhost:5432/app",
        poolclass="async_adapted_queue",     # the default is "null" — no pooling
    )
    uow = AsyncSQLAlchemyUnitOfWork(manager.session_maker, transaction_factory=Transaction)

    async with uow.transaction() as tx:      # commits on exit, rolls back on exception
        await tx.users.add("user@example.com")

    async with uow.query() as qx:            # read only: writes here are discarded
        users = (await qx.session.execute(select(UserDB))).scalars().all()

    await manager.aclose()


asyncio.run(main())
```

With the `settings` extra, `create_async_session_manager(config)` builds the same manager
from a `PostgresSettingsProtocol` and fills in the pgbouncer-safe defaults
(`AsyncCConnection`, `application_name`, `search_path`, `jit`, statement caches) for you.

## The API

### Top-level exports

Everything in this table is importable as `from sqlalchemy_foundation_kit import <name>`.
Nothing else is: `implicit_reexport = false`, so anything not listed here must be imported
from the submodule named beside it further down.

| Group | Names |
|---|---|
| Session | `AsyncSessionManager`, `AsyncSessionManagerBuilder`, `create_async_session_manager`, `AsyncCConnection`, `try_advisory_xact_lock`, `retry_async_connection`, `RetryConfig`, `DEFAULT_RETRY_CONFIG`, `DEFAULT_HEALTHCHECK_QUERY` |
| Unit of work | `AsyncSQLAlchemyUnitOfWork`, `AsyncSQLAlchemyUowTransaction`, `AsyncUnitOfWork`, `AsyncUowTransaction`, `IsolationLevel`, `PostgresAdvisoryLockMixin`, `SupportsAdvisoryLock`, `SupportsSavepoint` |
| Base ORM | `Base`, `BaseTable`, `DatetimeColumnsMixin`, `DB_NAMING_CONVENTION`, `PydanticJSONB`, `GenericJSONDict`, `UnConstrainedEnum`, `load_orm_metadata` |
| Engine utilities | `build_engine_kwargs`, `resolve_pool_class`, `register_pool_class`, `PoolRegistry`, `PoolClassStr`, `configure_orjson_serialization` |
| Config protocols | `PostgresSettingsProtocol`, `ConnectionSettingsProtocol`, `PoolSettingsProtocol`, `QuerySettingsProtocol` |
| Metrics protocols | `PostgresMetricsProtocol`, `PoolStatsRecorder`, `CheckoutRecorder`, `ErrorRecorder` |
| Version | `__version__` |

### `AsyncSessionManager`

`AsyncSessionManager(url, echo=False, poolclass="null", session_class=None,
expire_on_commit=False, connect_args=None, isolation_level=None, pool_settings=None,
use_orjson=False, metrics=None, on_engine_created=None, dispose_timeout=30.0, **kwargs)` —
`**kwargs` reach `create_async_engine`.

| Member | What it does |
|---|---|
| `.engine` | the `AsyncEngine`, created in `__init__` |
| `.session_maker` | the `async_sessionmaker`; this is what the unit of work wants |
| `.get_session()` | async context manager yielding a session with no transaction started |
| `.get_transaction(isolation_level=None)` | **raises `TypeError` at 0.2.0** — see [broken at 0.2.0](#broken-at-020) |
| `await .aclose()` | disposes the engine under `asyncio.shield`, capped at `dispose_timeout`; idempotent, logs a warning on timeout |
| `async with manager:` | the same `aclose()` on exit |

After `aclose()`, `get_session()` and `get_transaction()` raise
`RuntimeError("AsyncSessionManager is closed")`.

`AsyncSessionManagerBuilder(url)` is the same object built fluently:
`.with_echo(bool)`, `.with_pool(poolclass, pool_settings=None)`,
`.with_session_class(cls)`, `.with_expire_on_commit(bool)`, `.with_connect_args(**kw)`,
`.with_isolation_level(str)`, `.with_metrics(m)`, `.with_callbacks(on_engine_created=fn)`,
`.with_json_serialization(orjson=True)`, `.with_extra_kwargs(**kw)`,
`.with_dispose_timeout(float)`, `.build()`. A builder is reusable: `build()` does not
consume it.

`create_async_session_manager(postgres_config, application_name=None, metrics=None,
on_engine_created=None, connection_class=None, extra_server_settings=None,
extra_connect_args=None, **kwargs)` takes a `PostgresSettingsProtocol` and returns a
manager. It defaults `connection_class` to `AsyncCConnection`, sets `server_settings` from
`application_name`, `jit` and `db_schema` (as `search_path`), and passes both statement
cache sizes through. Your keys in `extra_server_settings` / `extra_connect_args` win over
the library's.

`attach_metrics(engine, metrics)` — in `sqlalchemy_foundation_kit.session.manager`, not
re-exported — wires the pool listeners onto an engine you built yourself. The manager
calls it when `metrics` is passed. A raising metrics callback is logged and swallowed,
never propagated.

### The unit of work

`AsyncSQLAlchemyUnitOfWork(session_maker, transaction_factory, *, flush_before_commit=True)`.
`transaction_factory` is any `Callable[[AsyncSession], T]`; normally your
`AsyncSQLAlchemyUowTransaction` subclass.

| Method | Transaction | On clean exit | On exception | Yields |
|---|---|---|---|---|
| `transaction(isolation_level=None, flush_before_commit=None)` | `session.begin()` | flush, then **commit** | rollback | `T` |
| `managed_session(isolation_level=None)` | `await session.begin()` | nothing — **you** commit | rollback | `(T, AsyncSession)` |
| `query(isolation_level=None)` | none started | nothing; session closes | session closes | `T` |
| `open_session(isolation_level=None)` | none | nothing | nothing | `AsyncSession` |

`open_session` is the documented extension point: override it in a subclass to set a GUC,
an RLS context or a statement timeout on every session, calling `super().open_session(...)`
inside. `flush_before_commit=None` on `transaction()` falls back to the constructor value
(`True`), which flushes before the commit so an integrity error surfaces inside the block
rather than at exit. Every `isolation_level` argument in this table is broken at 0.2.0 —
see below.

`TracedAsyncUnitOfWork(session_maker, transaction_factory,
service_name="sqlalchemy-foundation-kit", *, flush_before_commit=True)` from
`sqlalchemy_foundation_kit.contrib.telemetry` subclasses it and wraps all three in spans
named `uow.transaction`, `uow.managed_session` and `uow.query`, with `db.operation` and
`db.isolation_level` attributes. Without OpenTelemetry installed it is a transparent
pass-through.

### The transaction object

| Member | Where it comes from |
|---|---|
| `.session` | `AsyncSQLAlchemyUowTransaction` — the `AsyncSession` this context owns |
| `.savepoint()` | `AsyncSQLAlchemyUowTransaction` — `async with tx.savepoint():`, a `begin_nested()` block |
| `await .try_advisory_lock(key)` | `PostgresAdvisoryLockMixin`, mixed in beside it |
| your repositories | properties you write on your own subclass |

`AsyncUowTransaction`, `SupportsSavepoint` and `SupportsAdvisoryLock` are `Protocol`s for
typing a transaction structurally in a use case that should not import the concrete class.

`await try_advisory_xact_lock(session, key)` is the same lock as a free function:
`pg_try_advisory_xact_lock`, non-blocking, returns `True` if taken, released at the end of
the transaction. `key` may be `str | int`; the integer is wrapped into signed 64-bit.
Read rule 8 before passing a string.

### Base ORM

| Name | What it is |
|---|---|
| `Base` | `DeclarativeBase` with `MetaData(naming_convention=DB_NAMING_CONVENTION)` and a `type_annotation_map` mapping `uuid.UUID` to `postgresql.UUID()` and `datetime.datetime` to `TIMESTAMP(timezone=True)` |
| `BaseTable` | `Base`, `__abstract__`, plus a `__repr__` printing every column |
| `DatetimeColumnsMixin` | `created_at` / `updated_at`, both `server_default=timezone('UTC', now())`, `updated_at` also `onupdate`. Index them with the class variables `__created_at_index__` / `__updated_at_index__`, both `False` by default |
| `DB_NAMING_CONVENTION` | `ix` `%(column_0_label)s_idx`, `uq` `%(table_name)s_%(column_0_name)s_key`, `ck` `%(table_name)s_%(constraint_name)s_check`, `fk` `%(table_name)s_%(column_0_name)s_fkey`, `pk` `%(table_name)s_pkey` |
| `PydanticJSONB(model_type)` | `TypeDecorator` over `JSONB`. Validates on write and on read; `model_type` is required. A row that no longer validates is logged and returned raw, not raised |
| `GenericJSONDict` | `dict[str, Any]`, for a JSONB column that needs no validation |
| `UnConstrainedEnum` | a `functools.partial` of `sqlalchemy.Enum` with `native_enum=False`, `create_constraint=False`, `validate_strings=True` — a `VARCHAR` column, so a new member needs no migration |
| `load_orm_metadata(models_modules, metadata=None)` | imports each module path so its models register, then returns `metadata` or `Base.metadata`. This is what an Alembic `env.py` calls |

### Engine utilities

`PoolRegistry` maps a name to a pool class: `null`, `queue`, `singleton_thread`,
`async_adapted_queue`, `fallback_async_adapted_queue`, `static`. `PoolRegistry.register(name,
cls, *, override=False)` (or `register_pool_class(...)`) adds one and raises `ValueError`
on a duplicate without `override=True`; `resolve_pool_class(name_or_class)` resolves one
and raises `ValueError` on an unknown name; `PoolRegistry.list_available()` lists them.
`PoolClassStr` is the `Literal` of the six built-ins.

`build_engine_kwargs(echo, poolclass, isolation_level, pool_settings, connect_args,
extra_kwargs, use_orjson=False)` assembles the `create_async_engine` keywords: it always
sets `pool_pre_ping` (from `pool_settings.pre_ping`, else `True`), copies non-`None` pool
settings to `pool_size` / `max_overflow` / `pool_recycle` / `pool_timeout`, drops `None`
values out of `connect_args`, and merges `extra_kwargs` last.
`configure_orjson_serialization()` returns the `json_serializer` / `json_deserializer`
pair and raises `ImportError` without orjson.

### Configuration

The core depends on protocols only. `PostgresSettingsProtocol` needs `connection`, `pool`,
`query`, `application_name`, `db_schema`, `use_orjson_serialization`, `jit` and
`to_dsn() -> str`; `ConnectionSettingsProtocol` needs `host`, `port`, `user`, `password`,
`database`; `PoolSettingsProtocol` needs `kind`, `size`, `max_overflow`, `pre_ping`,
`recycle`, `timeout`; `QuerySettingsProtocol` needs `echo`, `statement_cache_size`,
`prepared_statement_cache_size`, `isolation_level`. Any object with those attributes works
— dataclass, plain class, Pydantic model.

With the `settings` extra, `sqlalchemy_foundation_kit.contrib.settings` implements them:

| Model | Fields and defaults |
|---|---|
| `ConnectionSettings` | `host="localhost"`, `port=5432` (1–65535), `user="postgres"`, `password: SecretStr` **required**, `database: str` **required** |
| `PoolSettings` | `kind="async_adapted_queue"`, `size=10`, `max_overflow=20`, `pre_ping=True`, `recycle=3600`, `timeout=30.0`. `kind="static"` with `max_overflow > 0` raises |
| `QuerySettings` | `echo=False`, `statement_cache_size=0`, `prepared_statement_cache_size=0`, `isolation_level=None` |
| `BasePostgresConfig` | `connection` **required**, `pool`, `query`, `application_name: str` **required**, `db_schema=None`, `use_orjson_serialization=True`, `jit="off"`, `metrics_enabled=False`. `to_dsn(driver="asyncpg", mask_password=False)`; `__repr__` prints the masked DSN |
| `BasePostgresMigrationsConfig` | `postgres: BasePostgresConfig`, with `env_nested_delimiter="__"` and `extra="ignore"` |

`BasePostgresConfig` declares no `model_config` of its own, so it reads environment
variables only through the parent `BaseSettings` that holds it. Under
`BasePostgresMigrationsConfig` the names are `POSTGRES__CONNECTION__HOST`,
`POSTGRES__POOL__SIZE`, `POSTGRES__APPLICATION_NAME` — two underscores at every level.

### Observability and DI

| Import | Needs | What you get |
|---|---|---|
| `contrib.metrics.PostgresMetrics(prefix=None)` | `metrics` | the six gauges/histogram/counters below; pass it as `metrics=` to a manager |
| `contrib.telemetry.instrument_engine(engine, **kw)` | `telemetry` | the `on_engine_created` hook shape — traces one engine |
| `contrib.telemetry.instrument_sqlalchemy(engine=None, **kw)` | `telemetry` | `SQLAlchemyInstrumentor().instrument(...)`; `engine=None` means every engine |
| `contrib.telemetry.instrument_asyncpg(**kw)` | `telemetry` | `AsyncPGInstrumentor().instrument(...)` |
| `contrib.telemetry.TracedAsyncUnitOfWork` | `telemetry` | the traced unit of work described above |
| `contrib.di.AsyncDatabaseProvider(healthcheck_query="SELECT 1", retry_config=DEFAULT_RETRY_CONFIG)` | `dishka` | APP-scoped `AsyncSessionManager` and `async_sessionmaker`; runs the healthcheck at startup and `aclose()` at shutdown. Override `create_session_manager` to customise |
| `contrib.di.AsyncUnitOfWorkProvider()` | `dishka` | APP-scoped `AsyncUnitOfWork[AsyncSQLAlchemyUowTransaction]`. Override `create_uow` to use your transaction class |
| `contrib.di.PrometheusPostgresMetricsProvider()` | `dishka` + `metrics` | a `PostgresMetricsProtocol`, or `None` unless `postgres.metrics_enabled` |
| `contrib.dependency_injector.DatabaseContainer` | `dependency-injector` | `session_manager` (resource), `session_maker`, `uow`; configured with `postgres_config`, `metrics`, `healthcheck_query`, `retry_config` |
| `contrib.dependency_injector.AsyncDatabaseResourceProvider(config, metrics=None, ...)` | `dependency-injector` | `await .start()` / `await .stop()` for a lifecycle you drive yourself |
| `contrib.dependency_injector.PrometheusMetricsContainer` | `dependency-injector` + `metrics` | `postgres_metrics` from `metrics_settings`, `default_prefix`, `postgres_settings` |

`PostgresMetrics` publishes `postgres_db_pool_size`, `postgres_db_pool_checked_out`,
`postgres_db_pool_overflow` (gauges), `postgres_db_connection_checkout_duration_seconds`
(histogram), `postgres_db_connection_timeouts_total` and
`postgres_db_connection_errors_total{error_type}` (counters). A `prefix` is prepended with
an underscore and must match `^[a-zA-Z_][a-zA-Z0-9_]*$`.

`retry_async_connection(connect_func, service_name, config=DEFAULT_RETRY_CONFIG)` is the
startup retry the DI providers use, and is usable on its own: it awaits `connect_func()`
up to `config.max_retries` times, sleeping `retry_delay * 2 ** attempt` capped at
`max_backoff_delay`, and re-raises the last exception. `RetryConfig` is a frozen dataclass
— `max_retries=3`, `retry_delay=1.0`, `max_backoff_delay=60.0`. It is a function, not a
decorator.

## Rules that hold or break the code

1. **`asyncpg` must be installed even though nothing declares it.** `AsyncCConnection`
   imports it at module import time and the package `__init__` imports that, so on a clean
   `pip install sqlalchemy-foundation-kit` the very first `import sqlalchemy_foundation_kit`
   raises `ModuleNotFoundError: No module named 'asyncpg'`. Install `asyncpg` alongside it.
2. **PostgreSQL over asyncpg only.** The DSN is `postgresql+asyncpg://…`.
   `create_async_session_manager` passes an asyncpg-specific `connection_class` and
   asyncpg-specific `connect_args`; another driver rejects them.
3. **The default `poolclass` is `"null"` — no pooling at all.** That default is for tests.
   A service wants `"async_adapted_queue"`, either as `poolclass=` or as
   `PoolSettings.kind`, whose default is already correct.
4. **The commit belongs to the unit of work, never to a repository.** A repository
   `flush()`es; `transaction()` commits. A `session.commit()` inside a repository ends the
   transaction under everything else that was going to share it.
5. **`query()` throws writes away.** It starts no transaction and commits nothing, so the
   session's implicit transaction is rolled back at close. An `INSERT` issued there is
   silently gone — verified, not theorised. Use `transaction()` for anything that writes.
6. **One session, one task.** The session a context manager yields is not concurrency-safe:
   `asyncio.gather` over statements on the same `tx` raises
   `IllegalStateChangeError`. Fan out by opening a `transaction()` per task, not by sharing
   one. The `AsyncSessionManager` and the unit of work above it are safe to share —
   they hold a factory, not a connection.
7. **A transaction object must not outlive its block.** `tx`, `tx.session`, and any ORM
   instance still attached to that session are invalid after the `async with` exits; the
   session is closed and its connection is back in the pool. Return domain objects or
   detached data, never a live `tx`. Storing one on `self`, in a module global, or in a
   `ContextVar` that outlives the block is the same bug.
8. **A string advisory-lock key does not lock across processes.** `try_advisory_xact_lock`
   turns a `str` into an integer with Python's `hash()`, which is salted per process:
   three fresh interpreters produced three different keys for `"job"`. Two replicas of the
   same service therefore take *different* locks and both proceed. Pass a stable integer
   you computed yourself (`zlib.crc32(b"job")`, a hash digest, a constant) for anything
   that has to be exclusive beyond one process. The protocol and the mixin type `key` as
   `int` for this reason; only the free function accepts `str`.
9. **An advisory lock is only held while its transaction is.** `pg_try_advisory_xact_lock`
   releases at transaction end, so take it inside `transaction()` or `managed_session()`
   and do the protected work in the same block. Taking one in `query()` is a no-op with a
   `True` return.
10. **`managed_session()` commits nothing.** Leaving the block without calling
    `await session.commit()` rolls everything back at close, quietly. Use `transaction()`
    unless the commit decision genuinely depends on something you learn after writing.
11. **`savepoint()` re-raises.** `async with tx.savepoint():` rolls the block back and lets
    the exception through — the caller decides what a failed item means. Catch it, record
    the failure on the still-healthy surrounding transaction, and carry on. Without a
    savepoint, one failed statement poisons the whole PostgreSQL transaction, including the
    statement that would have recorded the failure.
12. **`expire_on_commit` defaults to `False`.** ORM instances stay readable after the
    commit, which is what makes returning data out of a `transaction()` block work at all.
    Turning it on means every attribute read after the commit hits a closed session.
13. **Extras are not optional where you use them.** `contrib.settings` needs `[settings]`,
    `contrib.metrics` needs `[metrics]`, `contrib.telemetry` needs `[telemetry]`,
    `contrib.di` needs `[dishka]`, `contrib.dependency_injector` needs
    `[dependency-injector]`, and `use_orjson=True` needs `[orjson]`. The DI packages fail
    on *import* without their extra, with a bare `AttributeError` rather than the intended
    message — see below.
14. **Metrics never raise into your code.** Every recorder call is wrapped: a broken
    metrics backend is logged at exception level and discarded, and the query proceeds.
15. **Close the manager.** `await manager.aclose()` disposes the engine under a shield and
    a `dispose_timeout` (30s). Skipping it leaks connections; calling it twice is fine.

### Broken at 0.2.0

Three published entry points raise before they reach the database. All three were run
against PostgreSQL 17 to confirm it.

| Call | What happens | Use instead |
|---|---|---|
| `manager.get_transaction()`, with or without `isolation_level` | `TypeError: Session.__init__() got an unexpected keyword argument 'execution_options'` — the argument is passed to the session factory unconditionally | `async with manager.get_session() as s, s.begin():`, or the unit of work |
| `uow.transaction(isolation_level=…)`, `uow.managed_session(isolation_level=…)`, `uow.query(isolation_level=…)` | `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()… isolation_level may not be altered` — the level is applied after the connection has autobegun | set the level on the engine: `AsyncSessionManager(..., isolation_level="SERIALIZABLE")` or `QuerySettings(isolation_level=...)` |
| `import sqlalchemy_foundation_kit.contrib.di` (or `.contrib.dependency_injector`) without its extra | `AttributeError: 'NoneType' object has no attribute 'APP'` (resp. `'DeclarativeContainer'`) instead of the intended `ImportError` | install the extra; the message is not the one the code meant to give you |

`IsolationLevel` itself is fine — `READ_UNCOMMITTED`, `READ_COMMITTED`, `REPEATABLE_READ`,
`SERIALIZABLE`, whose values are the PostgreSQL spellings with spaces — and so is
`normalize_isolation_level` in `sqlalchemy_foundation_kit.uow.sqlalchemy`, which accepts
either spelling in any case. It is only the plumbing that carries the value to a session
that is wrong.

## Common mistakes

```python
# WRONG — committing in the repository ends the transaction under everyone else
class UserRepository:
    async def add(self, email: str) -> UserDB:
        user = UserDB(email=email)
        self._session.add(user)
        await self._session.commit()

# RIGHT — flush here, commit at the boundary
class UserRepository:
    async def add(self, email: str) -> UserDB:
        user = UserDB(email=email)
        self._session.add(user)
        await self._session.flush()
        return user
```

```python
# WRONG — query() starts no transaction, so this INSERT is rolled back at close
async with uow.query() as qx:
    await qx.users.add("user@example.com")

# RIGHT
async with uow.transaction() as tx:
    await tx.users.add("user@example.com")
```

```python
# WRONG — one session driven by four tasks: IllegalStateChangeError
async with uow.transaction() as tx:
    await asyncio.gather(*(tx.users.add(e) for e in emails))

# RIGHT — a transaction, and therefore a connection, per task
async def add(email: str) -> None:
    async with uow.transaction() as tx:
        await tx.users.add(email)

await asyncio.gather(*(add(e) for e in emails))
```

```python
# WRONG — the session is closed by the time the caller reads the attribute
async def get_user(uow, user_id):
    async with uow.query() as qx:
        return await qx.users.get(user_id)      # a live ORM instance

# RIGHT — leave the block with data, not with a session-bound object
async def get_user(uow, user_id) -> User | None:
    async with uow.query() as qx:
        row = await qx.users.get(user_id)
        return User(id=row.id, email=row.email) if row else None
```

```python
# WRONG — a string key hashes differently in every process, so nothing is excluded
async with uow.transaction() as tx:
    if await tx.try_advisory_lock("nightly-rollup"):
        ...

# RIGHT — a key both replicas compute the same way
LOCK_NIGHTLY_ROLLUP = 0x6E52  # any fixed int; zlib.crc32(b"nightly-rollup") works too

async with uow.transaction() as tx:
    if await tx.try_advisory_lock(LOCK_NIGHTLY_ROLLUP):
        ...
```

```python
# WRONG — retry_async_connection is not a decorator, and RetryConfig has other names
@retry_async_connection(config=RetryConfig(max_attempts=5, initial_delay=1.0))
async def connect(): ...

# RIGHT
await retry_async_connection(
    connect_func=connect,
    service_name="PostgreSQL",
    config=RetryConfig(max_retries=5, retry_delay=1.0, max_backoff_delay=30.0),
)
```

```python
# WRONG — the default pool is NullPool: a new connection for every session
manager = AsyncSessionManager("postgresql+asyncpg://…")

# RIGHT
manager = AsyncSessionManager("postgresql+asyncpg://…", poolclass="async_adapted_queue")
```

## Errors

The library defines no exception classes of its own. It raises the standard ones and lets
SQLAlchemy's through untouched.

| Raised | When |
|---|---|
| `ModuleNotFoundError` | `asyncpg` is not installed (rule 1) |
| `ImportError` | an extra is missing: `orjson`, `pydantic-settings`, `prometheus-client`, the OpenTelemetry instrumentations, `dishka`, `dependency-injector`. The orjson message names a `[json]` extra that does not exist — the real one is `[orjson]` |
| `RuntimeError` | `"AsyncSessionManager is closed"` — a session asked for after `aclose()` |
| `ValueError` | an isolation level `normalize_isolation_level` does not know; an unregistered pool name; a pool name registered twice without `override=True`; `max_retries < 1`; a metric prefix that is not a Prometheus identifier |
| `pydantic.ValidationError` | a `contrib.settings` model built without `password`, `database` or `application_name`, or a `static` pool with `max_overflow > 0` |
| `TypeError` | `manager.get_transaction()` (see above); a value orjson cannot serialize |
| `sqlalchemy.exc.IllegalStateChangeError` | one session driven by two tasks at once (rule 6) |
| `sqlalchemy.exc.InvalidRequestError` | `isolation_level` on a unit-of-work method (see above) |
| `sqlalchemy.exc.IntegrityError`, `OperationalError`, … | the database refused the statement. Inside `tx.savepoint()` these are re-raised with the surrounding transaction still usable; anywhere else they roll the whole block back |

## Documentation map

Fetch a page when the task is the one named beside it.

| Page | Read it when |
|---|---|
| [Home](index.md) | placing the library in a stack — what it covers and what each extra adds |
| [Quick start](guide/quickstart.md) | writing the first integration: config, model, repository, use case |
| [Configuration](guide/configuration.md) | every settings field, pool sizing, pgbouncer, protocol-based config |
| [Advanced usage](guide/advanced.md) | savepoints, advisory locks, metrics, tracing, both DI integrations |
| [API reference](reference/index.md) | an exact signature or docstring — HTML only, see above |
| [Changelog](changelog.md) | what changed between versions |
