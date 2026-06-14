# Ansible content

Mount your real Ansible content over this directory:

```bash
docker run --rm -v "$PWD/my-ansible:/automation/ansible" \
    ghcr.io/zollo/docker-automation:latest ansible site.yml
```

## Layout the toolbox understands

```
ansible/
├── site.yml            # playbooks at the top level are auto-discovered
├── playbooks/          # …as are playbooks under playbooks/
│   └── deploy.yml
├── inventory           # auto-attached with -i when present (file or dir)
├── group_vars/
├── host_vars/
└── roles/
```

* **Playbooks** — any `*.yml` / `*.yaml` at the top level or under `playbooks/`
  is offered in the web UI and resolvable by `automation ansible <name>`.
* **Inventory** — a file or directory named `inventory` is passed automatically
  via `-i` unless you specify your own.
* **Collections / roles** — declare shared dependencies in
  `requirements/ansible-requirements.yml` so they are installed into the image.

## Run from the console

```bash
automation ansible site.yml --limit web --extra-vars 'env=stage'
```

The sample `site.yml` and `inventory` here target `localhost` and require no
network, so they work as an immediate smoke test.
