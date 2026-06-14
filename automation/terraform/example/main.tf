# Sample Terraform project — no providers, no network, no real resources.
# Uses the built-in `terraform_data` resource so `init`/`plan`/`apply` work
# offline as a smoke test. Replace with (or mount over) your own project.

terraform {
  required_version = ">= 1.4.0"
}

variable "env" {
  description = "Example input variable."
  type        = string
  default     = "dev"
}

resource "terraform_data" "greeting" {
  input = "hello from the automation container (env=${var.env})"
}

output "greeting" {
  value = terraform_data.greeting.output
}
