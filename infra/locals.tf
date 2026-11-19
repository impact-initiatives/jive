locals {
  api_image    = "${var.container_registry_username}.azurecr.io/${var.image_repository_api}:${var.image_tag_api}"
  worker_image = "${var.container_registry_username}.azurecr.io/${var.image_repository_worker}:${var.image_tag_worker_validator}"

  tags = {
    environment = var.environment_name
    managed_by  = "opentofu"
    bl          = "IMPHQ4"
    state       = "safe-to-delete"
  }
}