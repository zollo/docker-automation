# Requirements

Placeholder files that let you declare everything that should be installed
into the container **without editing the Dockerfile**.

| File                        | Purpose                                                        | Installed with            |
| --------------------------- | -------------------------------------------------------------- | ------------------------- |
| `ansible-requirements.yml`  | Ansible Galaxy **collections** and **roles**                   | `ansible-galaxy install`  |
| `python-requirements.txt`   | Python packages: module deps, SDKs, custom plugin requirements | `pip install`             |

## When are these installed?

1. **At build time** — copied in and installed so they are baked into the image
   (this is what the CI/CD pipeline publishes to GHCR).
2. **At runtime** — run `automation install` inside the container, or start the
   container with `INSTALL_REQUIREMENTS_ON_START=true`. This is handy when you
   mount this directory in and want to add a collection/package without
   rebuilding the image:

   ```bash
   docker run --rm -v "$PWD/requirements:/opt/automation/requirements" \
       ghcr.io/zollo/docker-automation:latest install
   ```

Both files are safe to leave empty.

## Terraform providers

Terraform providers are **not** listed here. They are declared in the
`required_providers` block of each Terraform project and fetched automatically
by `terraform init`. To pre-cache providers into the image, add a
`terraform init` step for your project in the Dockerfile, or use a provider
mirror.
