# sqlalchemy-foundation-kit for AI agents

> One page holding everything a coding assistant needs to wire and drive
> sqlalchemy-foundation-kit correctly, plus a map of where the rest of the documentation
> keeps the details it leaves out. Give an agent this page rather than the whole site.

| | |
|---|---|
| Package | `sqlalchemy-foundation-kit` on PyPI, import root `sqlalchemy_foundation_kit` |
| Requires | Python 3.11+, SQLAlchemy 2 (`>=2.0.35,<3`), Pydantic 2 (`>=2.5,<3`), asyncpg (`>=0.30,<1`), PostgreSQL |
| Install | `pip install sqlalchemy-foundation-kit` · extras: `settings`, `metrics`, `orjson`, `dishka`, `dependency-injector`, `telemetry`, `all` |
| Async | the whole library. `AsyncEngine`, `AsyncSession`, `asyncpg` |
| Sync | none. There is no sync mirror and no sync entry point |
| Version | everything below was read from the source this site was built from. Some calls described here do not work on 0.2.0 or 0.2.1 — see [fixed since 0.2.0](#fixed-since-020) |
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
is the section correctness lives in, and it is followed by the short list of calls that
are [fixed since 0.2.0](#fixed-since-020) — on the version each row names, those fail
before they reach the database. Every name used below is in the public API; if you
need something not listed here, fetch the page the [documentation map](#documentation-map)
points at rather than guessing a method that sounds plausible.

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
from a `PostgresSettingsProtocol` and fills in the PgBouncer-safe defaults for you:
`AsyncCConnection`, both statement caches at 0, `application_name` as the only startup
parameter, and `db_schema` applied per transaction as `search_path` (rule 16).

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
| Metrics protocols | `PostgresMetricsProtocol`, `PoolStatsRecorder`, `CheckoutRecorder`, `CheckoutWaitRecorder`, `ErrorRecorder` |
| Version | `__version__` |

### `AsyncSessionManager`

`AsyncSessionManager(url, echo=False, poolclass="null", session_class=None,
expire_on_commit=False, connect_args=None, isolation_level=None, pool_settings=None,
use_orjson=False, metrics=None, on_engine_created=None, dispose_timeout=30.0,
search_path=None, **kwargs)` — `**kwargs` reach `create_async_engine`. `search_path`
attaches a `begin` listener to the engine that runs `set_config('search_path', …, true)` —
`SET LOCAL` — as the first statement of every transaction, autobegun ones included;
nothing is attached when it is `None`.

| Member | What it does |
|---|---|
| `.engine` | the `AsyncEngine`, created in `__init__` |
| `.session_maker` | the `async_sessionmaker`; this is what the unit of work wants |
| `.get_session()` | async context manager yielding a session with no transaction started |
| `.get_transaction(isolation_level=None)` | async context manager yielding a session with a transaction open: commits on clean exit, rolls back on exception. An `isolation_level` is set on that transaction's connection and nothing else |
| `await .aclose()` | disposes the engine under `asyncio.shield`, capped at `dispose_timeout`; idempotent, logs a warning on timeout |
| `async with manager:` | the same `aclose()` on exit |

After `aclose()`, `get_session()` and `get_transaction()` raise
`RuntimeError("AsyncSessionManager is closed")`.

`AsyncSessionManagerBuilder(url)` is the same object built fluently:
`.with_echo(bool)`, `.with_pool(poolclass, pool_settings=None)`,
`.with_session_class(cls)`, `.with_expire_on_commit(bool)`, `.with_connect_args(**kw)`,
`.with_isolation_level(str)`, `.with_metrics(m)`, `.with_callbacks(on_engine_created=fn)`,
`.with_json_serialization(orjson=True)`, `.with_extra_kwargs(**kw)`,
`.with_dispose_timeout(float)`, `.with_search_path(str)`, `.build()`. A builder is
reusable: `build()` does not consume it.

`create_async_session_manager(postgres_config, application_name=None, metrics=None,
on_engine_created=None, connection_class=None, extra_server_settings=None,
extra_connect_args=None, **kwargs)` takes a `PostgresSettingsProtocol` and returns a
manager. It defaults `connection_class` to `AsyncCConnection`, sends `application_name` —
and `jit`, only when the config sets it — as `server_settings`, hands `db_schema` to the
manager as `search_path`, and passes both statement cache sizes through. Your keys in
`extra_server_settings` / `extra_connect_args` win over the library's; `server_settings`
are startup parameters, so read rule 16 before adding one.

`attach_metrics(engine, metrics)` and `attach_search_path(engine, search_path)` — in
`sqlalchemy_foundation_kit.session.manager`, not re-exported — wire the pool listeners,
respectively the per-transaction `search_path`, onto an engine you built yourself. The
manager calls them when `metrics` / `search_path` is passed. A raising metrics callback is
logged and swallowed, never propagated.

`instrument_pool_class(pool_class, metrics)` lives beside them and is the other half of the
metrics wiring: it returns a subclass of `pool_class` that times `Pool.connect()`, which is
the only place the wait for a connection and the pool checkout timeout are visible — no
pool event fires for either. The manager applies it to whatever `resolve_pool_class`
returned whenever `metrics` implements `CheckoutWaitRecorder`, so callers get it without
asking. On an engine you build yourself, pass the result as `poolclass=` to
`create_async_engine`; `attach_metrics` logs a warning if you did not, rather than leaving
a wait histogram that never moves.

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
rather than at exit. An `isolation_level` argument takes an `IsolationLevel` or a string
in either spelling, and is set on the connection the block checks out, so it covers this
transaction and leaves the engine alone. Setting it has to happen before the transaction
starts, so it opens the transaction as the block is entered — `query()` included.

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
the transaction. `key` may be `str | int`; an integer is wrapped into signed 64-bit, a
string is hashed into it with BLAKE2b, reproducibly — the same string is the same lock in
every process. The `SupportsAdvisoryLock` protocol still types `key` as `int`; the mixin
and the free function take `str | int`.

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
| `BasePostgresConfig` | `connection` **required**, `pool`, `query`, `application_name: str` **required**, `db_schema=None`, `use_orjson_serialization=True`, `jit=None`, `metrics_enabled=False`. `to_dsn(driver="asyncpg", mask_password=False)`; `__repr__` prints the masked DSN. `db_schema` is a `search_path` value applied per transaction (rule 16); `jit` is a startup parameter and is sent only when set |
| `BasePostgresMigrationsConfig` | `postgres: BasePostgresConfig`, with `env_nested_delimiter="__"` and `extra="ignore"` |

`BasePostgresConfig` declares no `model_config` of its own, so it reads environment
variables only through the parent `BaseSettings` that holds it. Under
`BasePostgresMigrationsConfig` the names are `POSTGRES__CONNECTION__HOST`,
`POSTGRES__POOL__SIZE`, `POSTGRES__APPLICATION_NAME` — two underscores at every level.

### Observability and DI

| Import | Needs | What you get |
|---|---|---|
| `contrib.metrics.PostgresMetrics(prefix=None)` | `metrics` | the eight series below; pass it as `metrics=` to a manager |
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

`PostgresMetrics` publishes:

| Series | Type | What it measures |
|---|---|---|
| `postgres_db_pool_size` | gauge | connections the pool holds |
| `postgres_db_pool_checked_out` | gauge | connections currently in use |
| `postgres_db_pool_overflow` | gauge | connections over `pool_size`, within `max_overflow` |
| `postgres_db_connection_checkout_wait_seconds` | histogram | how long a caller **waited** for a connection — the queue wait, plus the pre-ping and the connect handshake when the pool had to grow. Buckets run to 30 s, the default `pool_timeout` |
| `postgres_db_connection_held_duration_seconds` | histogram | how long a caller **held** one, checkout to checkin — the query time seen from the pool |
| `postgres_db_connection_checkout_duration_seconds` | histogram | **deprecated**, and never measured what its name says: it is the held duration under its old name. Kept for one more minor release, then dropped. Move dashboards to `…_held_duration_seconds`, or to `…_checkout_wait_seconds` if what you wanted was the wait |
| `postgres_db_connection_timeouts_total` | counter | pool checkout timeouts, plus `TimeoutError`s seen by `handle_error` |
| `postgres_db_connection_errors_total{error_type}` | counter | database errors by exception class name |

A `prefix` is prepended with an underscore and must match `^[a-zA-Z_][a-zA-Z0-9_]*$`.

The wait histogram and the pool-timeout half of the counter come from the instrumented pool
class, not from a listener, so they move only on an engine built by `AsyncSessionManager`
or one whose pool went through `instrument_pool_class`.

`retry_async_connection(connect_func, service_name, config=DEFAULT_RETRY_CONFIG)` is the
startup retry the DI providers use, and is usable on its own: it awaits `connect_func()`
up to `config.max_retries` times, sleeping `retry_delay * 2 ** attempt` capped at
`max_backoff_delay`, and re-raises the last exception. `RetryConfig` is a frozen dataclass
— `max_retries=3`, `retry_delay=1.0`, `max_backoff_delay=60.0`. It is a function, not a
decorator.

## Rules that hold or break the code

1. **`asyncpg` is a hard dependency, not an extra.** `AsyncCConnection` subclasses
   `asyncpg.Connection` at module import time and the package `__init__` imports it, so
   the package cannot be imported without asyncpg. `pip install sqlalchemy-foundation-kit`
   brings it. On 0.2.0 it did not, and the first `import sqlalchemy_foundation_kit` raised
   `ModuleNotFoundError: No module named 'asyncpg'`.
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
8. **A string advisory-lock key is stable across processes; on 0.2.0 it was not.**
   `try_advisory_xact_lock` hashes a `str` with BLAKE2b, so every replica turns the same
   string into the same lock. On 0.2.0 it used Python's `hash()`, which is salted per
   process: three fresh interpreters produced three different keys for `"job"`, so two
   replicas took *different* locks and both proceeded. On that version pass a stable
   integer you computed yourself (`zlib.crc32(b"job")`, a digest, a constant) instead.
   Either way the key changes with the hash: a rolling deploy across the fix has old and
   new replicas holding different locks for the same name until it finishes.
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
    on *import* without their extra, with an `ImportError` naming the extra to install.
14. **Metrics never raise into your code.** Every recorder call is wrapped: a broken
    metrics backend is logged at exception level and discarded, and the query proceeds.
15. **Close the manager.** `await manager.aclose()` disposes the engine under a shield and
    a `dispose_timeout` (30s). Skipping it leaks connections; calling it twice is fine.
16. **Through PgBouncer in transaction mode, only `SET LOCAL` and the server's own settings
    hold.** asyncpg `server_settings` are startup parameters. PgBouncer forwards the ones it
    tracks (`client_encoding`, `datestyle`, `timezone`, `standard_conforming_strings`,
    `application_name`, plus `track_extra_parameters`), refuses the connection on any other
    (`unsupported startup parameter: jit`), and with `ignore_startup_parameters` drops them
    silently. So `jit` defaults to `None` and is sent only when set, and `db_schema` is
    applied with `SET LOCAL search_path` as the first statement of every transaction — each
    `transaction()`, `query()`, `managed_session()`, `get_session()`, `get_transaction()`
    and `engine.connect()` block, and the transaction after a `commit()` in the same
    session. Not covered: a statement under `isolation_level="AUTOCOMMIT"`, which begins no
    transaction. To have the schema without the round-trip use `ALTER ROLE … SET
    search_path`, `ALTER DATABASE … SET`, or schema-qualified metadata. A plain `SET` on a
    connection leaks to the next client through a pooler; never issue one in a `connect`
    listener. Statement caches stay at 0 and `AsyncCConnection` stays, for PgBouncer before
    1.22 (`max_prepared_statements=0`); 1.22+ tracks prepared statements itself.
17. **The wait for a connection and the time it was held are different metrics.** Alert on
    `postgres_db_connection_checkout_wait_seconds` — a rising wait is a pool about to run
    out, and `postgres_db_connection_timeouts_total` is what it turns into. The held
    duration, `postgres_db_connection_held_duration_seconds`, is query latency seen from
    the pool: it rises when the database slows down, whether or not the pool is under
    pressure. `postgres_db_connection_checkout_duration_seconds` is the held duration under
    a name that says wait; it is deprecated, and reading it as the wait is the mistake it
    invites.

### Fixed since 0.2.0

Three published entry points raise before they reach the database on 0.2.0; on 0.2.1 the
PgBouncer-safe defaults cannot connect through PgBouncer; and up to 0.3.0 the pool metrics
do not say what their names say. All are right on current versions; the workaround column
is what to do on the version the row names.

| Call | What it does on that version | Workaround there |
|---|---|---|
| `manager.get_transaction()`, with or without `isolation_level` (0.2.0) | `TypeError: Session.__init__() got an unexpected keyword argument 'execution_options'` — the argument was passed to the session factory unconditionally | `async with manager.get_session() as s, s.begin():`, or the unit of work |
| `uow.transaction(isolation_level=…)`, `uow.managed_session(isolation_level=…)`, `uow.query(isolation_level=…)` (0.2.0) | `InvalidRequestError: This connection has already initialized a SQLAlchemy Transaction()… isolation_level may not be altered` — the level was applied after the connection had autobegun | set the level on the engine: `AsyncSessionManager(..., isolation_level="SERIALIZABLE")` or `QuerySettings(isolation_level=...)` |
| `import sqlalchemy_foundation_kit.contrib.di` (or `.contrib.dependency_injector`) without its extra (0.2.0) | `AttributeError: 'NoneType' object has no attribute 'APP'` (resp. `'DeclarativeContainer'`) instead of the intended `ImportError` | install the extra; the message is not the one the code meant to give you |
| `create_async_session_manager(config)` through PgBouncer in transaction mode (0.2.1 and earlier) | `jit="off"` was the default and `db_schema` went as `search_path`, both as startup parameters: a default PgBouncer refuses every connection with `ProtocolViolationError: unsupported startup parameter: jit`; with `ignore_startup_parameters=jit,search_path` it connects and silently drops both, so every query lands in `public` | `jit=None`, `db_schema=None`, and `ALTER ROLE … SET search_path` on the server |
| `postgres_db_connection_timeouts_total` (0.3.0 and earlier) | stayed at zero through every pool checkout timeout. The counter was fed only from the engine's `handle_error` listener, and a pool `TimeoutError` is raised by `pool.connect()` before any DBAPI call, so it never reaches that listener — the one timeout a pool actually produces under load was the one the counter did not count | count `sqlalchemy.exc.TimeoutError` around your own session calls |
| `postgres_db_connection_checkout_duration_seconds` (0.3.0 and earlier) | the only checkout histogram there was, and it measures the time between the `checkout` and `checkin` events — how long a connection was *held*, which is query duration seen from the pool. The time a caller waited for a connection, which is what the name suggests and what predicts a pool outage, was not exposed at all | none; the wait was not measurable from outside the pool |

`IsolationLevel` itself was always fine — `READ_UNCOMMITTED`, `READ_COMMITTED`,
`REPEATABLE_READ`, `SERIALIZABLE`, whose values are the PostgreSQL spellings with spaces —
and so is `normalize_isolation_level` in `sqlalchemy_foundation_kit.uow.sqlalchemy`, which
accepts either spelling in any case. It was only the plumbing carrying the value to a
session that was wrong.

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
# WRONG — the lock is released at transaction end, so this protects nothing
async with uow.query() as qx:
    if await qx.try_advisory_lock("nightly-rollup"):
        ...
await do_the_rollup()          # outside the block: the lock is already gone

# RIGHT — take the lock and do the work in the same transaction
async with uow.transaction() as tx:
    if await tx.try_advisory_lock("nightly-rollup"):
        await do_the_rollup(tx)
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

```python
# WRONG — both are startup parameters; PgBouncer in transaction mode refuses the connection,
# or with ignore_startup_parameters drops them and every query lands in public
config = BasePostgresConfig(..., jit="off")                      # "for pgbouncer"
manager = create_async_session_manager(config, extra_server_settings={"search_path": "app"})

# RIGHT — send nothing PgBouncer will not carry; the schema is applied per transaction
config = BasePostgresConfig(..., db_schema="app")                # jit stays None
manager = create_async_session_manager(config)
```

## Errors

The library defines no exception classes of its own. It raises the standard ones and lets
SQLAlchemy's through untouched.

| Raised | When |
|---|---|
| `ModuleNotFoundError` | `asyncpg` is not installed — only reachable on 0.2.0, which did not declare it (rule 1) |
| `ImportError` | an extra is missing: `orjson`, `pydantic-settings`, `prometheus-client`, the OpenTelemetry instrumentations, `dishka`, `dependency-injector`. The message names the extra to install |
| `RuntimeError` | `"AsyncSessionManager is closed"` — a session asked for after `aclose()` |
| `ValueError` | an isolation level `normalize_isolation_level` does not know; an unregistered pool name; a pool name registered twice without `override=True`; `max_retries < 1`; a metric prefix that is not a Prometheus identifier |
| `pydantic.ValidationError` | a `contrib.settings` model built without `password`, `database` or `application_name`, or a `static` pool with `max_overflow > 0` |
| `TypeError` | a value orjson cannot serialize; `manager.get_transaction()` on 0.2.0 (see above) |
| `sqlalchemy.exc.IllegalStateChangeError` | one session driven by two tasks at once (rule 6) |
| `sqlalchemy.exc.InvalidRequestError` | `isolation_level` on a unit-of-work method on 0.2.0 (see above) |
| `asyncpg.exceptions.ProtocolViolationError` | `unsupported startup parameter: …` — a `server_settings` key PgBouncer does not track (rule 16); on 0.2.1 the default `jit` did this on every connection |
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
