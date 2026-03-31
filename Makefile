PYTHON ?= python3

.PHONY: refresh-installer
refresh-installer:
	$(PYTHON) scripts/update_installer_payload.py
