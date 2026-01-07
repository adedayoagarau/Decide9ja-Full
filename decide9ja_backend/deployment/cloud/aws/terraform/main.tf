# Decide9ja AWS Infrastructure
# Terraform configuration for running scheduler on AWS
#
# Components:
# - ECS Fargate for scheduler container
# - CloudWatch Events for cron triggers
# - Lambda for lightweight jobs
# - RDS PostgreSQL
# - ElastiCache Redis
# - Secrets Manager for API keys

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "decide9ja-terraform-state"
    key    = "scheduler/terraform.tfstate"
    region = "eu-west-1"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "Decide9ja"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ============================================
# Variables
# ============================================

variable "aws_region" {
  description = "AWS region"
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name"
  default     = "production"
}

variable "anthropic_api_key" {
  description = "Anthropic API key"
  type        = string
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  sensitive   = true
}

# ============================================
# VPC & Networking
# ============================================

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "decide9ja-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24"]

  enable_nat_gateway = true
  single_nat_gateway = true

  enable_dns_hostnames = true
  enable_dns_support   = true
}

# ============================================
# Secrets Manager
# ============================================

resource "aws_secretsmanager_secret" "api_keys" {
  name                    = "decide9ja/api-keys"
  recovery_window_in_days = 7
}

resource "aws_secretsmanager_secret_version" "api_keys" {
  secret_id = aws_secretsmanager_secret.api_keys.id
  secret_string = jsonencode({
    ANTHROPIC_API_KEY = var.anthropic_api_key
    OPENAI_API_KEY    = var.openai_api_key
  })
}

# ============================================
# RDS PostgreSQL
# ============================================

resource "aws_db_subnet_group" "main" {
  name       = "decide9ja-db-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "rds" {
  name        = "decide9ja-rds-sg"
  description = "Security group for RDS"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
}

resource "aws_db_instance" "main" {
  identifier           = "decide9ja-db"
  engine               = "postgres"
  engine_version       = "15"
  instance_class       = "db.t3.micro"
  allocated_storage    = 20
  storage_encrypted    = true

  db_name  = "decide9ja"
  username = "decide9ja"
  password = random_password.db_password.result

  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name

  backup_retention_period = 7
  skip_final_snapshot     = var.environment != "production"

  tags = {
    Name = "decide9ja-database"
  }
}

resource "random_password" "db_password" {
  length  = 32
  special = false
}

# ============================================
# ElastiCache Redis
# ============================================

resource "aws_elasticache_subnet_group" "main" {
  name       = "decide9ja-redis-subnet"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name        = "decide9ja-redis-sg"
  description = "Security group for Redis"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }
}

resource "aws_elasticache_cluster" "main" {
  cluster_id           = "decide9ja-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [aws_security_group.redis.id]
  subnet_group_name    = aws_elasticache_subnet_group.main.name
}

# ============================================
# ECR Repository
# ============================================

resource "aws_ecr_repository" "scheduler" {
  name                 = "decide9ja-scheduler"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

# ============================================
# ECS Cluster
# ============================================

resource "aws_ecs_cluster" "main" {
  name = "decide9ja-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

resource "aws_security_group" "ecs_tasks" {
  name        = "decide9ja-ecs-tasks-sg"
  description = "Security group for ECS tasks"
  vpc_id      = module.vpc.vpc_id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ============================================
# ECS Task Definition - Scheduler
# ============================================

resource "aws_ecs_task_definition" "scheduler" {
  family                   = "decide9ja-scheduler"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = 512
  memory                   = 1024
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name  = "scheduler"
      image = "${aws_ecr_repository.scheduler.repository_url}:latest"

      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql://${aws_db_instance.main.username}:${random_password.db_password.result}@${aws_db_instance.main.endpoint}/${aws_db_instance.main.db_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${aws_elasticache_cluster.main.cache_nodes[0].address}:6379"
        }
      ]

      secrets = [
        {
          name      = "ANTHROPIC_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:ANTHROPIC_API_KEY::"
        },
        {
          name      = "OPENAI_API_KEY"
          valueFrom = "${aws_secretsmanager_secret.api_keys.arn}:OPENAI_API_KEY::"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.scheduler.name
          awslogs-region        = var.aws_region
          awslogs-stream-prefix = "ecs"
        }
      }
    }
  ])
}

# ============================================
# ECS Service - Scheduler
# ============================================

resource "aws_ecs_service" "scheduler" {
  name            = "decide9ja-scheduler"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.scheduler.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.ecs_tasks.id]
  }
}

# ============================================
# CloudWatch Logs
# ============================================

resource "aws_cloudwatch_log_group" "scheduler" {
  name              = "/ecs/decide9ja-scheduler"
  retention_in_days = 30
}

# ============================================
# IAM Roles
# ============================================

resource "aws_iam_role" "ecs_execution" {
  name = "decide9ja-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "ecs_execution_secrets" {
  name = "secrets-access"
  role = aws_iam_role.ecs_execution.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue"
      ]
      Resource = aws_secretsmanager_secret.api_keys.arn
    }]
  })
}

resource "aws_iam_role" "ecs_task" {
  name = "decide9ja-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
    }]
  })
}

# ============================================
# Outputs
# ============================================

output "database_endpoint" {
  value     = aws_db_instance.main.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "ecr_repository_url" {
  value = aws_ecr_repository.scheduler.repository_url
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
