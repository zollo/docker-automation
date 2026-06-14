#!/usr/bin/env bash
#
# Install user-declared requirements (Python packages + Ansible collections /
# roles) from the requirements directory. Safe to run repeatedly and safe when
# the requirements files are empty.
#
set -euo pipefail

REQ_DIR="${AUTOMATION_REQUIREMENTS_DIR:-${AUTOMATION_APP:-/opt/automation}/requirements}"
PY_REQ="${REQ_DIR}/python-requirements.txt"
GALAXY_REQ="${REQ_DIR}/ansible-requirements.yml"
COLLECTIONS_PATH="${ANSIBLE_COLLECTIONS_PATH:-/usr/share/ansible/collections}"
ROLES_PATH="${ANSIBLE_ROLES_PATH:-/usr/share/ansible/roles}"

log() { printf '\033[1;34m[install]\033[0m %s\n' "$*"; }

if [ -f "$PY_REQ" ]; then
    log "Installing Python requirements from ${PY_REQ}"
    pip install --no-cache-dir -r "$PY_REQ"
else
    log "No python-requirements.txt found, skipping Python packages."
fi

if [ -f "$GALAXY_REQ" ]; then
    log "Installing Ansible collections from ${GALAXY_REQ} into ${COLLECTIONS_PATH}"
    ansible-galaxy collection install -r "$GALAXY_REQ" -p "$COLLECTIONS_PATH" || true
    log "Installing Ansible roles from ${GALAXY_REQ} into ${ROLES_PATH}"
    ansible-galaxy role install -r "$GALAXY_REQ" -p "$ROLES_PATH" || true
else
    log "No ansible-requirements.yml found, skipping Galaxy content."
fi

log "Requirements installation complete."
