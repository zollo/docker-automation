#!/usr/bin/env bash
#
# Container entrypoint. Dispatches to the automation CLI, a raw tool
# invocation, the optional web interface, or an interactive shell.
#
# The web interface is entirely optional: every capability is reachable
# from the console without it.
#
set -euo pipefail

AUTOMATION_APP="${AUTOMATION_APP:-/opt/automation}"

# Optionally (re)install user requirements at container start. Useful when
# requirements files are mounted in rather than baked into the image.
if [ "${INSTALL_REQUIREMENTS_ON_START:-false}" = "true" ]; then
    "${AUTOMATION_APP}/scripts/install-requirements.sh" || true
fi

cmd="${1:-help}"

case "$cmd" in
    web)
        shift
        exec "${AUTOMATION_APP}/scripts/run-web.sh" "$@"
        ;;
    automation)
        shift
        exec "${AUTOMATION_APP}/bin/automation" "$@"
        ;;
    install)
        exec "${AUTOMATION_APP}/scripts/install-requirements.sh"
        ;;
    # Raw tool passthrough — `docker run IMG ansible --version`,
    # `docker run IMG terraform plan`, etc. For the logged, mount-aware
    # wrappers use the `automation` subcommand (e.g. `automation ansible site.yml`).
    ansible|ansible-playbook|ansible-galaxy|ansible-vault|ansible-inventory|ansible-lint|ansible-config|ansible-doc)
        exec "$@"
        ;;
    terraform)
        exec "$@"
        ;;
    shell|bash)
        exec /bin/bash
        ;;
    sh)
        exec /bin/sh
        ;;
    help|--help|-h)
        exec "${AUTOMATION_APP}/bin/automation" help
        ;;
    *)
        # Anything else is run verbatim, so `docker run ... <any command>` works.
        exec "$@"
        ;;
esac
