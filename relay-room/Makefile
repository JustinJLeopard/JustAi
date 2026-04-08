RELAY_DB_NAME ?= $(shell if [ -f .relay-db-target ]; then cat .relay-db-target; else echo relay-room-dev; fi)
RELAY_SERVER ?= local-server
RELAY_INSTALL_STAMP ?= $(HOME)/.local/share/relay-room/install-source.sha256

.PHONY: build-module publish generate install check-install setup-hooks start board test test-e2e log-rotate sprint-scorecard

build-module:
	spacetime build --module-path spacetimedb

publish:
	spacetime publish --no-config --server $(RELAY_SERVER) --module-path ./spacetimedb $(RELAY_DB_NAME) -y

generate:
	spacetime generate --module-path ./spacetimedb --lang rust --out-dir ./client/src/module_bindings -y

install:
	bash -lc 'source "$$HOME/.cargo/env" 2>/dev/null || true; cargo install --path ./client --force --root "$$HOME/.local"'
	@mkdir -p "$(dir $(RELAY_INSTALL_STAMP))"
	@src_hash=$$({ \
		find client/src spacetimedb/src -type f -print 2>/dev/null; \
		for extra in client/Cargo.toml spacetimedb/Cargo.toml; do \
			[ -f "$$extra" ] && printf '%s\n' "$$extra"; \
		done; \
	} | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1); \
	printf '%s\n' "$$src_hash" > "$(RELAY_INSTALL_STAMP)"

check-install:
	@binary="$(HOME)/.local/bin/relay"; \
	if [ ! -x "$$binary" ]; then \
		echo "relay binary missing - run make install"; \
		exit 1; \
	fi; \
	if [ ! -f "$(RELAY_INSTALL_STAMP)" ]; then \
		echo "relay install stamp missing - run make install"; \
		exit 1; \
	fi; \
	src_hash=$$({ \
		find client/src spacetimedb/src -type f -print 2>/dev/null; \
		for extra in client/Cargo.toml spacetimedb/Cargo.toml; do \
			[ -f "$$extra" ] && printf '%s\n' "$$extra"; \
		done; \
	} | sort | xargs sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1); \
	installed_hash=$$(cat "$(RELAY_INSTALL_STAMP)"); \
	if [ "$$src_hash" != "$$installed_hash" ]; then \
		echo "relay binary may be stale - run make install"; \
		exit 1; \
	fi; \
	echo "relay binary is current"

setup-hooks:
	bash scripts/setup_hooks.sh

start:
	bash scripts/start_relay_room.sh

board:
	RELAY_DB_NAME=$(RELAY_DB_NAME) RELAY_SERVER=$(RELAY_SERVER) $(HOME)/.local/bin/relay board

test:
	bash tests/test_relay_dispatch.sh
	bash tests/test_dispatch_daemon.sh
	bash tests/test_daemon_ctl.sh
	python3 -m unittest -v tests/test_relay_web.py
	python3 -m unittest -v tests/test_relay_web_v2.py
	python3 -m unittest -v tests/test_health_server.py
	bash tests/test_model_audit.sh
	bash -lc 'source "$$HOME/.cargo/env" 2>/dev/null || true; cd client && cargo test'

test-e2e:
	bash tests/test_e2e_pipeline.sh

log-rotate:
	bash scripts/log_archive.sh --rotate

sprint-scorecard:
	@if [ -z "$(SPRINT)" ]; then \
		echo "usage: make sprint-scorecard SPRINT=7"; \
		exit 1; \
	fi
	bash scripts/sprint_scorecard.sh "$(SPRINT)"
