.PHONY: test build smoke-opencode smoke-claude lint validate

test:
	uv run --with pytest pytest tests/py -q
	cd opencode && npm test

build:
	cd opencode && npm run build

smoke-opencode:
	bash tests/smoke/opencode.sh

smoke-claude:
	bash tests/smoke/claude.sh

lint:
	jq empty hooks/hooks.json codex/hooks.json .claude-plugin/*.json
	shellcheck install.sh tests/smoke/*.sh

validate:
	claude plugin validate .
