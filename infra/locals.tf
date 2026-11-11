locals {
  api_image    = "${var.registry_server}/${var.image_repository_api}:${var.image_tag_api}"
  worker_image = "${var.registry_server}/${var.image_repository_worker}:${var.image_tag_worker}"

  tags = {
    environment = var.environment_name
    managed_by  = "opentofu"
  }
}