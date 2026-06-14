# Terraform content

Mount your real Terraform projects over this directory. Each subdirectory that
contains `*.tf` files is treated as a project:

```
terraform/
├── example/        # the bundled no-op sample project
│   └── main.tf
├── network/
│   └── main.tf
└── app/
    └── main.tf
```

## Run from the console

```bash
automation terraform example init
automation terraform example plan
automation terraform example apply        # adds -auto-approve for you
automation terraform example destroy
```

`automation terraform <project> <cmd>` runs `terraform` inside
`/automation/terraform/<project>`, logging output to `/automation/logs`.

## Run from the web UI

Pick the project, choose an action (`plan`, `apply`, …) and run it. For
`plan`/`apply`/`destroy` the UI auto-runs `terraform init` first when the
project hasn't been initialised yet.

## Providers

Providers are declared per project in `required_providers` and fetched by
`terraform init`. The bundled `example` project uses the built-in
`terraform_data` resource so it needs **no** provider downloads and works
offline as a smoke test.

> State, `.terraform/` caches and lock files are git-ignored — keep real state
> in a remote backend.
