variable "region" {
  description = "AWS region for the infrastructure"
  default     = "eu-west-2" # London
}

variable "environment" {
  description = "Deployment environment"
  default     = "dev"
}

variable "gpu_instance_type" {
  description = "GPU instance type for the node group"
  default     = "g4dn.xlarge" # 1x T4, cheapest GPU
}

variable "gpu_max_nodes" {
  description = "Maximum number of GPU nodes"
  default     = 2
}

variable "use_spot" {
  description = "Use EC2 Spot instances for GPU nodes"
  default     = true
}
