"""Unit tests for PostgreSQL settings."""

from __future__ import annotations

import pytest

# Skip all tests if pydantic-settings is not installed
pytest.importorskip("pydantic")
pytest.importorskip("pydantic_settings")

from pydantic import SecretStr, ValidationError

from sqlalchemy_foundation_kit.contrib.settings.postgres import (
    BasePostgresConfig,
    BasePostgresMigrationsConfig,
    ConnectionSettings,
    PoolSettings,
    QuerySettings,
)

# ============================================================================
# ConnectionSettings Tests
# ============================================================================


@pytest.mark.unit
def test__connection_settings__default_values__succeeds() -> None:
    # Arrange & Act
    settings = ConnectionSettings(
        password=SecretStr("secret"),
        database="testdb",
    )

    # Assert
    assert settings.host == "localhost"
    assert settings.port == 5432
    assert settings.user == "postgres"
    assert settings.password.get_secret_value() == "secret"
    assert settings.database == "testdb"


@pytest.mark.unit
def test__connection_settings__custom_values__succeeds() -> None:
    # Arrange & Act
    settings = ConnectionSettings(
        host="db.example.com",
        port=5433,
        user="dbuser",
        password=SecretStr("mypassword"),
        database="mydb",
    )

    # Assert
    assert settings.host == "db.example.com"
    assert settings.port == 5433
    assert settings.user == "dbuser"
    assert settings.password.get_secret_value() == "mypassword"
    assert settings.database == "mydb"


@pytest.mark.unit
def test__connection_settings__invalid_port_too_low__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
            port=0,
        )


@pytest.mark.unit
def test__connection_settings__invalid_port_too_high__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
            port=65536,
        )


@pytest.mark.unit
def test__connection_settings__missing_password__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        ConnectionSettings(database="testdb")  # type: ignore[call-arg]


@pytest.mark.unit
def test__connection_settings__missing_database__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        ConnectionSettings(password=SecretStr("secret"))  # type: ignore[call-arg]


# ============================================================================
# PoolSettings Tests
# ============================================================================


@pytest.mark.unit
def test__pool_settings__default_values__succeeds() -> None:
    # Arrange & Act
    settings = PoolSettings()

    # Assert
    assert settings.kind == "async_adapted_queue"
    assert settings.size == 10
    assert settings.max_overflow == 20
    assert settings.pre_ping is True
    assert settings.recycle == 3600
    assert settings.timeout == 30.0


@pytest.mark.unit
def test__pool_settings__custom_values__succeeds() -> None:
    # Arrange & Act
    settings = PoolSettings(
        kind="null",
        size=20,
        max_overflow=10,
        pre_ping=False,
        recycle=7200,
        timeout=60.0,
    )

    # Assert
    assert settings.kind == "null"
    assert settings.size == 20
    assert settings.max_overflow == 10
    assert settings.pre_ping is False
    assert settings.recycle == 7200
    assert settings.timeout == 60.0


@pytest.mark.unit
def test__pool_settings__static_pool_with_max_overflow__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError, match="max_overflow must be 0 for static pool"):
        PoolSettings(kind="static", max_overflow=10)


@pytest.mark.unit
def test__pool_settings__static_pool_with_zero_overflow__succeeds() -> None:
    # Arrange & Act
    settings = PoolSettings(kind="static", max_overflow=0)

    # Assert
    assert settings.kind == "static"
    assert settings.max_overflow == 0


@pytest.mark.unit
def test__pool_settings__negative_size__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        PoolSettings(size=0)


@pytest.mark.unit
def test__pool_settings__negative_max_overflow__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        PoolSettings(max_overflow=-1)


@pytest.mark.unit
def test__pool_settings__negative_timeout__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        PoolSettings(timeout=-1.0)


# ============================================================================
# QuerySettings Tests
# ============================================================================


@pytest.mark.unit
def test__query_settings__default_values__succeeds() -> None:
    # Arrange & Act
    settings = QuerySettings()

    # Assert
    assert settings.echo is False
    assert settings.statement_cache_size == 0
    assert settings.prepared_statement_cache_size == 0
    assert settings.isolation_level is None


@pytest.mark.unit
def test__query_settings__custom_values__succeeds() -> None:
    # Arrange & Act
    settings = QuerySettings(
        echo=True,
        statement_cache_size=100,
        prepared_statement_cache_size=200,
        isolation_level="READ COMMITTED",
    )

    # Assert
    assert settings.echo is True
    assert settings.statement_cache_size == 100
    assert settings.prepared_statement_cache_size == 200
    assert settings.isolation_level == "READ COMMITTED"


@pytest.mark.unit
def test__query_settings__all_isolation_levels__succeed() -> None:
    # Arrange
    levels = ["READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE"]

    # Act & Assert
    for level in levels:
        settings = QuerySettings(isolation_level=level)  # type: ignore[arg-type]
        assert settings.isolation_level == level


@pytest.mark.unit
def test__query_settings__negative_cache_size__raises_error() -> None:
    # Arrange & Act & Assert
    with pytest.raises(ValidationError):
        QuerySettings(statement_cache_size=-1)


# ============================================================================
# BasePostgresConfig Tests
# ============================================================================


@pytest.mark.unit
def test__base_postgres_config__minimal_required_fields__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
        ),
        application_name="test-service",
    )

    # Assert
    assert config.connection.host == "localhost"
    assert config.connection.database == "testdb"
    assert config.application_name == "test-service"
    assert config.pool.size == 10
    assert config.query.echo is False


@pytest.mark.unit
def test__base_postgres_config__custom_all_settings__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="db.example.com",
            port=5433,
            user="dbuser",
            password=SecretStr("mypassword"),
            database="mydb",
        ),
        pool=PoolSettings(size=20, max_overflow=30),
        query=QuerySettings(echo=True, isolation_level="SERIALIZABLE"),
        application_name="my-service",
        db_schema="public",
        use_orjson_serialization=False,
        jit="on",
        metrics_enabled=True,
    )

    # Assert
    assert config.connection.host == "db.example.com"
    assert config.connection.port == 5433
    assert config.pool.size == 20
    assert config.pool.max_overflow == 30
    assert config.query.echo is True
    assert config.query.isolation_level == "SERIALIZABLE"
    assert config.application_name == "my-service"
    assert config.db_schema == "public"
    assert config.use_orjson_serialization is False
    assert config.jit == "on"
    assert config.metrics_enabled is True


@pytest.mark.unit
def test__base_postgres_config__to_dsn_default__returns_asyncpg_dsn() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("testpass"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    dsn = config.to_dsn()

    # Assert
    assert dsn == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"


@pytest.mark.unit
def test__base_postgres_config__to_dsn_with_custom_driver__returns_custom_dsn() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("testpass"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    dsn = config.to_dsn(driver="psycopg")

    # Assert
    assert dsn == "postgresql+psycopg://testuser:testpass@localhost:5432/testdb"


@pytest.mark.unit
def test__base_postgres_config__to_dsn_without_driver__returns_plain_dsn() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("testpass"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    dsn = config.to_dsn(driver=None)

    # Assert
    assert dsn == "postgresql://testuser:testpass@localhost:5432/testdb"


@pytest.mark.unit
def test__base_postgres_config__to_dsn_masked__returns_masked_password() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("testpass"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    dsn = config.to_dsn(mask_password=True)

    # Assert
    assert dsn == "postgresql+asyncpg://testuser:**********@localhost:5432/testdb"
    assert "testpass" not in dsn


@pytest.mark.unit
def test__base_postgres_config__to_dsn_special_chars_in_password__url_encoded() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("test@pass:word#123"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    dsn = config.to_dsn()

    # Assert
    # @ should be encoded as %40, : as %3A, # as %23
    assert "test%40pass%3Aword%23123" in dsn


@pytest.mark.unit
def test__base_postgres_config__repr__masks_password() -> None:
    # Arrange
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            host="localhost",
            port=5432,
            user="testuser",
            password=SecretStr("secret123"),
            database="testdb",
        ),
        application_name="test",
    )

    # Act
    repr_str = repr(config)

    # Assert
    assert "**********" in repr_str
    assert "secret123" not in repr_str
    assert "BasePostgresConfig" in repr_str


@pytest.mark.unit
def test__base_postgres_config__default_jit_off__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
        ),
        application_name="test",
    )

    # Assert
    assert config.jit == "off"


@pytest.mark.unit
def test__base_postgres_config__jit_on__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
        ),
        application_name="test",
        jit="on",
    )

    # Assert
    assert config.jit == "on"


@pytest.mark.unit
def test__base_postgres_config__jit_none__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresConfig(
        connection=ConnectionSettings(
            password=SecretStr("secret"),
            database="testdb",
        ),
        application_name="test",
        jit=None,
    )

    # Assert
    assert config.jit is None


# ============================================================================
# BasePostgresMigrationsConfig Tests
# ============================================================================


@pytest.mark.unit
def test__base_postgres_migrations_config__basic__succeeds() -> None:
    # Arrange & Act
    config = BasePostgresMigrationsConfig(
        postgres=BasePostgresConfig(
            connection=ConnectionSettings(
                password=SecretStr("secret"),
                database="testdb",
            ),
            application_name="migrations",
        ),
    )

    # Assert
    assert config.postgres.application_name == "migrations"
    assert config.postgres.connection.database == "testdb"


@pytest.mark.unit
def test__base_postgres_migrations_config__extra_fields_ignored() -> None:
    # Arrange & Act
    config = BasePostgresMigrationsConfig(
        postgres=BasePostgresConfig(
            connection=ConnectionSettings(
                password=SecretStr("secret"),
                database="testdb",
            ),
            application_name="migrations",
        ),
        extra_field="ignored",  # type: ignore[call-arg]
    )

    # Assert
    # Should not raise error, extra fields are ignored
    assert config.postgres.application_name == "migrations"
