# Optional managed Postgres (var.use_rds). Off by default: it is the single
# largest line on this stack's bill, about as much as the instance itself.
#
# Deliberately the cheapest shape that is still a real RDS instance: single-AZ,
# smallest Graviton class, 20 GB gp3, no Performance Insights, one day of
# automated backups, no final snapshot. Every one of those is a thing a real
# deployment would turn the other way.
#
# Gotcha: Postgres 15 and later on RDS default to `rds.force_ssl = 1`. asyncpg
# negotiates TLS by default (sslmode=prefer), so the app connects without a
# change, but a client configured with sslmode=disable is refused with a
# pg_hba error that does not mention TLS.

resource "aws_db_subnet_group" "main" {
  count      = var.use_rds ? 1 : 0
  name       = local.name
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  count = var.use_rds ? 1 : 0

  identifier     = "${local.name}-db"
  engine         = "postgres"
  engine_version = "16"
  instance_class = var.rds_instance_class

  allocated_storage = 20
  storage_type      = "gp3"
  storage_encrypted = true

  db_name  = "raindb"
  username = "rain"
  password = random_password.db[0].result

  db_subnet_group_name   = aws_db_subnet_group.main[0].name
  vpc_security_group_ids = [aws_security_group.db[0].id]
  publicly_accessible    = false
  multi_az               = false

  backup_retention_period      = 1
  performance_insights_enabled = false
  auto_minor_version_upgrade   = true
  apply_immediately            = true

  # Built to be destroyed. A real database wants the opposite of all three.
  skip_final_snapshot      = true
  deletion_protection      = false
  delete_automated_backups = true
}
