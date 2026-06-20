# Releasing

This project publishes a multi-arch container image to the GitHub Container
Registry (GHCR). The CI/CD pipeline in [`.github/workflows/ci.yml`](.github/workflows/ci.yml)
handles building, testing, and publishing.

## What publishes when

| Trigger                          | Tags pushed to `ghcr.io/zollo/docker-automation` |
| -------------------------------- | ------------------------------------------------ |
| Push to `main` (default branch)  | `latest`, `main`, `sha-<short>`                  |
| Push to any other branch         | `<branch-name>`, `sha-<short>`                   |
| Push a `v*` tag (e.g. `v1.2.3`)  | `1.2.3`, `1.2`, `sha-<short>`                    |
| Pull request                     | builds & smoke-tests only — **no push**          |

`latest` only ever tracks the default branch (`main`) — it is gated by
`is_default_branch`, so tag and feature-branch pushes never move it.

Tagging is the only step needed to cut a versioned release; the pipeline does
the rest.

## Cutting a release

1. Make sure `main` is green and points at the commit you want to release.

2. Create an annotated [semver](https://semver.org/) tag and push it:

   ```bash
   git fetch origin
   git checkout main && git pull --ff-only

   git tag -a v1.0.0 -m "v1.0.0 — Ansible + Terraform automation container"
   git push origin v1.0.0
   ```

   Pushing the tag triggers the workflow, which publishes
   `ghcr.io/zollo/docker-automation:1.0.0` and `:1.0`.

3. (Optional) Create the GitHub Release with notes:

   ```bash
   gh release create v1.0.0 \
     --title "v1.0.0 — Ansible + Terraform automation container" \
     --notes "See CHANGELOG / commit history for details."
   ```

   Or use **Releases → Draft a new release** in the GitHub UI and select the
   `v1.0.0` tag.

## Verifying

```bash
docker pull ghcr.io/zollo/docker-automation:1.0.0
docker run --rm ghcr.io/zollo/docker-automation:1.0.0 version
```

Check the published tags under the repository's **Packages** section, and the
workflow run under **Actions** for the green publish.

## Notes

- The image is built for `linux/amd64` and `linux/arm64`.
- Terraform's version is set by the `TERRAFORM_VERSION` build arg (default in
  the `Dockerfile`); bump it there if a release should ship a new Terraform.
- A cache-export hiccup from the GitHub Actions cache backend will **not** fail
  a publish (the `cache-to` exporters use `ignore-error=true`).
