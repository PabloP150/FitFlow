###############################################################################
# FitFlow — despliegue en AWS (punto extra)
#
# Arquitectura: una instancia EC2 corriendo el MISMO docker-compose.yml que se
# usa en local, con los secretos en AWS Systems Manager Parameter Store en vez
# de un archivo .env versionado.
#
# El enunciado permite explicitamente esta opcion ("Los servicios como
# contenedores en ECS Fargate o en una instancia EC2 con Docker Compose").
# Se eligio EC2 porque:
#   - Son 11 contenedores, 3 de ellos PostgreSQL. En RDS serian 3 instancias
#     gestionadas, muy por encima de la capa gratuita.
#   - El docker-compose.yml local funciona tal cual, sin reescribir nada:
#     mismo networking interno, mismo Consul, mismos Agent Cards.
#   - Cabe en la capa gratuita (t3.micro + EBS), que era el requisito de costo.
#
# Todo lo que se crea aqui se destruye con `terraform destroy`.
###############################################################################

terraform {
  required_version = ">= 1.5"
  required_providers {
    aws    = { source = "hashicorp/aws", version = "~> 5.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
    }
  }
}

###############################################################################
# Red propia
#
# La cuenta no tiene VPC por defecto (se puede borrar, y en cuentas nuevas a
# veces no viene), asi que se crea una minima en vez de depender del estado
# previo de la cuenta: el `terraform apply` funciona en cualquier cuenta vacia.
#
# Es una subnet publica simple: la instancia recibe IP publica y sale por el
# Internet Gateway. No hace falta NAT Gateway (que ademas costaria ~$32/mes).
###############################################################################

resource "aws_vpc" "fitflow" {
  cidr_block           = "10.20.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "fitflow" {
  vpc_id = aws_vpc.fitflow.id
  tags   = { Name = "${var.project_name}-igw" }
}

data "aws_availability_zones" "available" {
  state = "available"
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.fitflow.id
  cidr_block              = "10.20.1.0/24"
  availability_zone       = data.aws_availability_zones.available.names[0]
  map_public_ip_on_launch = true
  tags                    = { Name = "${var.project_name}-public" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.fitflow.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.fitflow.id
  }

  tags = { Name = "${var.project_name}-public" }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Amazon Linux 2023: trae dnf, systemd y soporte de SSM Agent preinstalado.
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-2023.*-x86_64"]
  }
}

###############################################################################
# Secretos — Parameter Store (SecureString)
#
# Se usa Parameter Store y no Secrets Manager porque los parametros estandar
# son gratuitos, mientras que Secrets Manager cobra ~$0.40 por secreto/mes.
# Ambos son "el servicio de secrets del proveedor"; el cambio a Secrets Manager
# seria directo si hiciera falta rotacion automatica.
#
# Las contrasenas se generan aca: nunca las escribe una persona ni viajan por
# el repo.
###############################################################################

resource "random_password" "jwt_secret" {
  length  = 48
  special = false
}

resource "random_password" "db" {
  for_each = toset(["users", "booking", "notif"])
  length   = 24
  special  = false
}

locals {
  ssm_prefix = "/${var.project_name}"

  # Secretos generados por Terraform.
  generated_secrets = merge(
    { "JWT_SECRET_KEY" = random_password.jwt_secret.result },
    { for k, v in random_password.db : "${upper(k)}_DB_PASSWORD" => v.result }
  )
}

resource "aws_ssm_parameter" "secret" {
  for_each = local.generated_secrets

  name  = "${local.ssm_prefix}/${each.key}"
  type  = "SecureString"
  value = each.value
  tier  = "Standard" # gratuito
}

# La API key de Gemini se maneja aparte: si no se pasa por variable, se crea un
# placeholder y el valor real se setea con `aws ssm put-parameter --overwrite`,
# de modo que la key nunca quede en el state de Terraform.
resource "aws_ssm_parameter" "gemini_api_key" {
  name  = "${local.ssm_prefix}/GEMINI_API_KEY"
  type  = "SecureString"
  value = var.gemini_api_key != "" ? var.gemini_api_key : "SET_ME_WITH_AWS_SSM_PUT_PARAMETER"
  tier  = "Standard"

  lifecycle {
    # No pisar un valor puesto a mano fuera de Terraform.
    ignore_changes = [value]
  }
}

###############################################################################
# IAM — la instancia lee sus propios secretos, nada mas
###############################################################################

data "aws_iam_policy_document" "assume_ec2" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "instance" {
  name               = "${var.project_name}-instance"
  assume_role_policy = data.aws_iam_policy_document.assume_ec2.json
}

data "aws_iam_policy_document" "read_secrets" {
  statement {
    sid     = "ReadFitFlowParameters"
    actions = ["ssm:GetParametersByPath", "ssm:GetParameter", "ssm:GetParameters"]
    resources = [
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}",
      "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${local.ssm_prefix}/*",
    ]
  }

  statement {
    sid       = "DecryptWithDefaultSsmKey"
    actions   = ["kms:Decrypt"]
    resources = ["*"]
    condition {
      test     = "StringEquals"
      variable = "kms:ViaService"
      values   = ["ssm.${var.aws_region}.amazonaws.com"]
    }
  }
}

data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "read_secrets" {
  name   = "${var.project_name}-read-secrets"
  role   = aws_iam_role.instance.id
  policy = data.aws_iam_policy_document.read_secrets.json
}

# Permite administrar la instancia con Session Manager sin abrir el puerto 22.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_instance_profile" "instance" {
  name = "${var.project_name}-instance"
  role = aws_iam_role.instance.name
}

###############################################################################
# Red — security group
###############################################################################

resource "aws_security_group" "fitflow" {
  name        = "${var.project_name}-sg"
  description = "Acceso publico a los servicios de FitFlow"
  vpc_id      = aws_vpc.fitflow.id
}

locals {
  # Puertos publicos: los 3 microservicios, el MCP server, Consul y los 3 agentes.
  public_ports = {
    "fitflow-mcp"        = 8000
    "booking-svc"        = 8001
    "notif-svc"          = 8002
    "users-svc"          = 8003
    "consul-ui"          = 8500
    "orchestrator-agent" = 9000
    "booking-agent"      = 9001
    "notification-agent" = 9002
  }
}

resource "aws_vpc_security_group_ingress_rule" "app" {
  for_each = local.public_ports

  security_group_id = aws_security_group.fitflow.id
  description       = each.key
  from_port         = each.value
  to_port           = each.value
  ip_protocol       = "tcp"
  cidr_ipv4         = var.allowed_cidr[0]
}

# Reglas extra si allowed_cidr trae mas de un bloque.
resource "aws_vpc_security_group_ingress_rule" "app_extra_cidrs" {
  for_each = {
    for pair in setproduct(keys(local.public_ports), slice(var.allowed_cidr, 1, length(var.allowed_cidr))) :
    "${pair[0]}-${pair[1]}" => { port = local.public_ports[pair[0]], cidr = pair[1], name = pair[0] }
  }

  security_group_id = aws_security_group.fitflow.id
  description       = each.value.name
  from_port         = each.value.port
  to_port           = each.value.port
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value.cidr
}

resource "aws_vpc_security_group_ingress_rule" "ssh" {
  for_each = toset(var.ssh_allowed_cidr)

  security_group_id = aws_security_group.fitflow.id
  description       = "SSH"
  from_port         = 22
  to_port           = 22
  ip_protocol       = "tcp"
  cidr_ipv4         = each.value
}

resource "aws_vpc_security_group_egress_rule" "all" {
  security_group_id = aws_security_group.fitflow.id
  description       = "Salida libre (pull de imagenes, API de Gemini, SSM)"
  ip_protocol       = "-1"
  cidr_ipv4         = "0.0.0.0/0"
}

###############################################################################
# Instancia
###############################################################################

resource "aws_instance" "fitflow" {
  ami                    = data.aws_ami.al2023.id
  instance_type          = var.instance_type
  iam_instance_profile   = aws_iam_instance_profile.instance.name
  vpc_security_group_ids = [aws_security_group.fitflow.id]
  subnet_id              = aws_subnet.public.id
  key_name               = var.ssh_key_name

  user_data_replace_on_change = true
  user_data = templatefile("${path.module}/user_data.sh", {
    repo_url    = var.repo_url
    repo_branch = var.repo_branch
    ssm_prefix  = local.ssm_prefix
    aws_region  = var.aws_region
  })

  root_block_device {
    volume_size = var.root_volume_size
    volume_type = "gp3"
    encrypted   = true
  }

  metadata_options {
    http_tokens = "required" # IMDSv2
  }

  tags = { Name = "${var.project_name}-server" }

  depends_on = [
    aws_ssm_parameter.secret,
    aws_ssm_parameter.gemini_api_key,
    aws_iam_role_policy.read_secrets,
  ]
}

# IP estable: no cambia si se reinicia la instancia, para que las URLs del
# README y del video sigan siendo validas.
# Ojo: una Elastic IP es gratuita mientras este asociada a una instancia EN
# EJECUCION. Si se apaga la instancia sin liberar la EIP, AWS cobra por ella.
resource "aws_eip" "fitflow" {
  instance = aws_instance.fitflow.id
  domain   = "vpc"
  tags     = { Name = "${var.project_name}-eip" }
}
