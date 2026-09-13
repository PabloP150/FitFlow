output "public_ip" {
  description = "IP publica (Elastic IP) de la instancia."
  value       = aws_eip.fitflow.public_ip
}

output "instance_id" {
  description = "Id de la instancia (para Session Manager)."
  value       = aws_instance.fitflow.id
}

output "urls" {
  description = "URLs publicas de cada componente de FitFlow."
  value = {
    dashboard_a2a      = "http://${aws_eip.fitflow.public_ip}:9000"
    consul_ui          = "http://${aws_eip.fitflow.public_ip}:8500/ui"
    users_svc          = "http://${aws_eip.fitflow.public_ip}:8003"
    booking_svc        = "http://${aws_eip.fitflow.public_ip}:8001"
    notif_svc          = "http://${aws_eip.fitflow.public_ip}:8002"
    mcp_server         = "http://${aws_eip.fitflow.public_ip}:8000/mcp"
    booking_agent_card = "http://${aws_eip.fitflow.public_ip}:9001/.well-known/agent.json"
    notif_agent_card   = "http://${aws_eip.fitflow.public_ip}:9002/.well-known/agent.json"
  }
}

output "next_steps" {
  description = "Que hacer despues del apply."
  value       = <<-EOT

    FitFlow desplegado en http://${aws_eip.fitflow.public_ip}

    1. El bootstrap tarda ~4-6 min (instalar docker, clonar, construir 7 imagenes).
       Seguirlo con:
         aws ssm start-session --target ${aws_instance.fitflow.id} --region ${var.aws_region}
         sudo tail -f /var/log/fitflow-bootstrap.log

    2. Setear la API key de Gemini (si no se paso por variable):
         aws ssm put-parameter --name ${local.ssm_prefix}/GEMINI_API_KEY \
           --value 'TU_KEY' --type SecureString --overwrite --region ${var.aws_region}
         aws ssm start-session --target ${aws_instance.fitflow.id} --region ${var.aws_region}
         sudo systemctl restart fitflow

    3. Verificar:
         curl http://${aws_eip.fitflow.public_ip}:8003/healthz
         curl http://${aws_eip.fitflow.public_ip}:9001/.well-known/agent.json

    4. Al terminar la demo, destruir todo para no gastar:
         terraform destroy
  EOT
}
