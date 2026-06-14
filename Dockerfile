# syntax=docker/dockerfile:1

############################################################
# Automation toolbox: Ansible + Terraform in one container #
############################################################
FROM python:3.12-slim AS base

# Version of Terraform to bake into the image. Override at build time:
#   docker build --build-arg TERRAFORM_VERSION=1.10.5 .
ARG TERRAFORM_VERSION=1.10.5
# Provided automatically by BuildKit (amd64/arm64) for multi-arch builds.
ARG TARGETARCH

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    AUTOMATION_HOME=/automation \
    AUTOMATION_APP=/opt/automation \
    ANSIBLE_COLLECTIONS_PATH=/usr/share/ansible/collections \
    ANSIBLE_ROLES_PATH=/usr/share/ansible/roles \
    PATH="/opt/automation/bin:${PATH}"

# ---------------------------------------------------------------------------
# System dependencies
# ---------------------------------------------------------------------------
# hadolint ignore=DL3008
RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        gnupg \
        jq \
        openssh-client \
        rsync \
        sshpass \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# ---------------------------------------------------------------------------
# Terraform (downloaded from the official HashiCorp releases)
# ---------------------------------------------------------------------------
RUN set -eux; \
    arch="${TARGETARCH:-amd64}"; \
    curl -fsSL -o /tmp/terraform.zip \
        "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_${arch}.zip"; \
    unzip -o /tmp/terraform.zip -d /usr/local/bin; \
    rm -f /tmp/terraform.zip; \
    terraform version

# ---------------------------------------------------------------------------
# Python tooling: Ansible (preinstalled) + the optional web interface stack.
# Requirements files are copied first so these layers cache well.
# ---------------------------------------------------------------------------
RUN pip install --no-cache-dir "ansible>=9,<12" "ansible-lint>=24"

COPY web/requirements.txt /tmp/web-requirements.txt
RUN pip install --no-cache-dir -r /tmp/web-requirements.txt

# User supplied Python plugins / SDKs (placeholder file, safe when empty)
COPY requirements/python-requirements.txt /tmp/python-requirements.txt
RUN pip install --no-cache-dir -r /tmp/python-requirements.txt

# User supplied Ansible collections & roles (placeholder file, safe when empty)
COPY requirements/ansible-requirements.yml /tmp/ansible-requirements.yml
RUN set -eux; \
    ansible-galaxy collection install -r /tmp/ansible-requirements.yml -p "${ANSIBLE_COLLECTIONS_PATH}"; \
    ansible-galaxy role install -r /tmp/ansible-requirements.yml -p "${ANSIBLE_ROLES_PATH}"

# ---------------------------------------------------------------------------
# Application code + CLI
# ---------------------------------------------------------------------------
COPY . ${AUTOMATION_APP}
RUN set -eux; \
    chmod +x ${AUTOMATION_APP}/entrypoint.sh ${AUTOMATION_APP}/bin/automation ${AUTOMATION_APP}/scripts/*.sh; \
    ln -sf ${AUTOMATION_APP}/bin/automation /usr/local/bin/automation

# Seed the mount points with the bundled sample content (overridden when the
# user mounts their own playbooks / projects over /automation/...).
RUN set -eux; \
    mkdir -p ${AUTOMATION_HOME}; \
    cp -a ${AUTOMATION_APP}/automation/. ${AUTOMATION_HOME}/; \
    mkdir -p ${AUTOMATION_HOME}/ansible ${AUTOMATION_HOME}/terraform ${AUTOMATION_HOME}/logs

WORKDIR ${AUTOMATION_HOME}

# Optional web interface
EXPOSE 8080

# Healthcheck for `web` mode. In CLI mode the container exits immediately, so
# this never runs; when the web server is up it must answer /api/health.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS "http://localhost:${WEB_PORT:-8080}/api/health" || exit 1

ENTRYPOINT ["/opt/automation/entrypoint.sh"]
CMD ["help"]
