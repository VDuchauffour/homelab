.PHONY: check-readme fix-readme warden-seed warden-seed-cleanup warden-delete warden-compare jellyfin-move jellyfin-move-dry-run jellyfin-update blueprint-update helm-update helm-update-all helm-diff helm-diff-all

warden-seed:
	@cd scripts && uv run warden-seed --apps-only --host http://warden.home.arpa

warden-seed-cleanup:
	@cd scripts && uv run warden-seed --apps-only --cleanup --host http://warden.home.arpa

warden-delete:
	@cd scripts && uv run warden-delete --force --host http://warden.home.arpa

warden-compare:
	@cd scripts && uv run warden-compare

jellyfin-move:
	@cd scripts && uv run jellyfin-move

jellyfin-move-dry-run:
	@cd scripts && uv run jellyfin-move --dry-run

jellyfin-update:
	@cd kubernetes/apps/jellyfin && helmfile apply
	@kubectl rollout restart deployment/jellyfin -n media-center

blueprint-update:
	@vals eval -f kubernetes/infra/pangolin-newt/manifests/blueprint.yaml | kubectl apply -f -
	@kubectl rollout restart deployment/fossorial-newt-main-tunnel -n fossorial

helm-update:
	@./scripts/helm-update.sh $(APP)

helm-update-all:
	@./scripts/helm-update.sh --all

helm-diff:
	@./scripts/helm-update.sh --diff $(APP)

helm-diff-all:
	@./scripts/helm-update.sh --diff --all

check-readme:
	@echo "Checking README.md tables against kubernetes/ directories..."
	@exit_code=0; \
	for dir in kubernetes/apps/*/; do \
		name=$$(basename "$$dir"); \
		if ! grep -q "| $$name |" README.md; then \
			echo "MISSING app: $$name"; \
			exit_code=1; \
		fi; \
	done; \
	for dir in kubernetes/infra/*/; do \
		name=$$(basename "$$dir"); \
		if ! grep -q "| $$name |" README.md; then \
			echo "MISSING infra: $$name"; \
			exit_code=1; \
		fi; \
	done; \
	if [ $$exit_code -eq 0 ]; then \
		echo "All directories are listed in README.md"; \
	else \
		echo ""; \
		echo "Run 'make fix-readme' to add missing entries."; \
	fi; \
	exit $$exit_code

fix-readme:
	@missing_apps=""; \
	missing_infra=""; \
	for dir in kubernetes/apps/*/; do \
		name=$$(basename "$$dir"); \
		if ! grep -q "| $$name |" README.md; then \
			missing_apps="$$missing_apps $$name"; \
		fi; \
	done; \
	for dir in kubernetes/infra/*/; do \
		name=$$(basename "$$dir"); \
		if ! grep -q "| $$name |" README.md; then \
			missing_infra="$$missing_infra $$name"; \
		fi; \
	done; \
	if [ -z "$$missing_apps" ] && [ -z "$$missing_infra" ]; then \
		echo "README.md is already up to date."; \
	else \
		echo "Missing apps:$$missing_apps"; \
		echo "Missing infra:$$missing_infra"; \
		opencode --prompt "Update README.md to add missing entries to the deployed components tables. The Apps table is inside a <details><summary>Apps</summary> block and the Infrastructure Tools table is inside a <details><summary>Infrastructure Tools</summary> block. Each row follows the pattern: | <img src=\"ICON_URL\" width=\"24\"> | name | Short description |. Add ONLY these missing entries, do NOT remove or modify existing rows. Missing apps:$$missing_apps. Missing infra:$$missing_infra. Look at each app/infra directory (helmfile.yaml, values.yaml, Chart.yaml) to write an accurate description and find a suitable icon URL (prefer https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/APP_NAME.png, fall back to the project GitHub raw icon, or as a last resort check kubernetes/apps/glance/values.yaml for icon/favicon URLs used in the Glance dashboard bookmarks, and if nothing else works use https://cdn.jsdelivr.net/gh/walkxcode/dashboard-icons/png/kubernetes.png)."; \
	fi
