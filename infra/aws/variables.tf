variable "aws_region" {
  description = "Region de AWS donde se despliega FitFlow."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefijo para nombrar los recursos."
  type        = string
  default     = "fitflow"
}

variable "instance_type" {
  description = <<-EOT
    Tipo de instancia EC2. t3.micro entra en la capa gratuita (750 h/mes
    durante 12 meses en cuentas elegibles) y alcanza para los 11 contenedores
    gracias al swap que configura user_data. Si la instancia va muy justa de
    memoria, subir a t3.small (ya fuera de free tier, ~$15/mes).
  EOT
  type        = string
  default     = "t3.micro"
}

variable "root_volume_size" {
  description = "Tamano del disco raiz en GB (la capa gratuita cubre 30 GB de EBS)."
  type        = number
  default     = 20
}

variable "repo_url" {
  description = "Repositorio git que la instancia clona al arrancar."
  type        = string
  default     = "https://github.com/PabloP150/FitFlow.git"
}

variable "repo_branch" {
  description = "Rama a desplegar."
  type        = string
  default     = "main"
}

variable "allowed_cidr" {
  description = <<-EOT
    Desde donde se puede acceder a los puertos de la aplicacion.
    0.0.0.0/0 deja el sistema accesible publicamente, que es justo lo que pide
    el enunciado ("sistema accesible por URL publica"). Para restringirlo a tu
    propia IP: ["A.B.C.D/32"].
  EOT
  type        = list(string)
  default     = ["0.0.0.0/0"]
}

variable "ssh_allowed_cidr" {
  description = <<-EOT
    Desde donde se permite SSH (puerto 22). Por defecto se deja cerrado:
    para administrar la instancia se usa AWS Systems Manager Session Manager,
    que no necesita abrir ningun puerto ni manejar llaves SSH.
  EOT
  type        = list(string)
  default     = []
}

variable "ssh_key_name" {
  description = "Nombre de un key pair existente en EC2 (opcional; solo si vas a usar SSH)."
  type        = string
  default     = null
}

variable "gemini_api_key" {
  description = <<-EOT
    API key de Gemini para el Orchestrator Agent.

    Dejalo vacio (recomendado): Terraform crea el parametro con un placeholder
    y despues lo seteas fuera del state con

      aws ssm put-parameter --name /fitflow/GEMINI_API_KEY \
        --value 'TU_KEY' --type SecureString --overwrite

    Asi la key nunca queda escrita en el archivo de estado de Terraform.
  EOT
  type        = string
  default     = ""
  sensitive   = true
}
