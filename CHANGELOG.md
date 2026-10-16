# Changelog

## [0.5.0](https://github.com/bedrock-python/sqlalchemy-foundation-kit/compare/sqlalchemy-foundation-kit-v0.4.0...sqlalchemy-foundation-kit-v0.5.0) (2026-10-16)


### ⚠ BREAKING CHANGES

* BasePostgresConfig.use_orjson_serialization now defaults to False, matching AsyncSessionManager and the builder. A service that has orjson installed, kept the default, and writes values only orjson serializes (datetime, UUID, Decimal, non-str keys) into JSON columns now gets StatementError (TypeError: Object of type datetime is not JSON serializable). Set use_orjson_serialization=True to keep the old behaviour.
* uow.query() now opens its transaction READ ONLY. A write inside it (INSERT, UPDATE, DELETE, DDL, nextval()) fails with SQLSTATE 25006 instead of being rolled back silently, or persisted when followed by an explicit session.commit(). Move writes to uow.transaction().

### Bug Fixes

* build null and static pools from PoolSettings, and stop recommending the sync queue pool ([#61](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/61)) ([608d327](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/608d32747361321895f6fc43f5e77da6937375ff))
* count connect timeouts, not statement timeouts, in connection_timeouts_total ([#63](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/63)) ([961e0e8](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/961e0e862cb540525cda99b5ecc79ee12cbab2e4))
* default use_orjson_serialization to False, so the [settings] quick start runs ([#66](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/66)) ([3addfdd](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/3addfdd50c98657966867b680121facd596b6810))
* read the pool gauges when they are scraped, and never export a negative overflow ([#62](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/62)) ([e85ac96](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/e85ac96bd875ee47729f029c8046ea85be48f712))
* run query() in a READ ONLY transaction, as documented ([#64](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/64)) ([cb77404](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/cb7740468cc86d1d7e9f7bda80d56b27b0300739))
* stop logging a failed flush's parameters and row values ([#65](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/65)) ([6dd88ba](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/6dd88ba34de6f6fa3306f7e9002788ab57f7797c))

## [0.4.0](https://github.com/bedrock-python/sqlalchemy-foundation-kit/compare/sqlalchemy-foundation-kit-v0.3.0...sqlalchemy-foundation-kit-v0.4.0) (2026-09-07)


### Features

* measure the wait for a pool connection, and count pool checkout timeouts ([#27](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/27)) ([78c9d7e](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/78c9d7e2c05052090276bce08219047849cd6dbb))

## [0.3.0](https://github.com/bedrock-python/sqlalchemy-foundation-kit/compare/sqlalchemy-foundation-kit-v0.2.1...sqlalchemy-foundation-kit-v0.3.0) (2026-09-07)


### Features

* stop sending jit and search_path as startup parameters ([#24](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/24)) ([704c343](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/704c343b932b15f0c6ee434f2fc80ab4732b0f80))

## [0.2.1](https://github.com/bedrock-python/sqlalchemy-foundation-kit/compare/sqlalchemy-foundation-kit-v0.2.0...sqlalchemy-foundation-kit-v0.2.1) (2026-09-06)


### Bug Fixes

* the defects the agents page turned up ([#21](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/21)) ([9548c72](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/9548c72670696dd68e0eeec1f0ae4ad896fa62d6))

## [0.2.0](https://github.com/bedrock-python/sqlalchemy-foundation-kit/compare/sqlalchemy-foundation-kit-v0.1.0...sqlalchemy-foundation-kit-v0.2.0) (2026-08-28)


### Features

* **uow:** add savepoint() to AsyncSQLAlchemyUowTransaction ([#6](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/6)) ([c46d881](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/c46d881052b7476211c31f4adc6058d4f5500b6a)), closes [#5](https://github.com/bedrock-python/sqlalchemy-foundation-kit/issues/5)


### Bug Fixes

* **ci:** add workflow_dispatch and created trigger to publish workflow ([142aef5](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/142aef5040777b31509e8d7b26f01774e8f22432))

## 0.1.0 (2026-05-19)


### Features

* add managed_session method for manual transaction control and tracing ([776407b](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/776407b5dbe78d314e7525bd68ae8c9c772f78a7))
* **contrib:** add dependency-injector support, rename di to dishka, add test suite ([3bbf3e4](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/3bbf3e46b8ecd0419652dc53d1cee7d1fdbf031b))
* initial sqlalchemy-foundation-kit library ([738b4f1](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/738b4f126e03d0e7dc8852d30b0cf76b67bbbc57))


### Bug Fixes

* comprehensive code review improvements ([487c283](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/487c2835e77c93cd64f9f00c73b7ae7a84673548))


### Documentation

* **foundation-kit:** add comprehensive documentation for all features ([8d10f84](https://github.com/bedrock-python/sqlalchemy-foundation-kit/commit/8d10f84179273a8cc40dc1fe326bddab84379d32))
