import consul as consul_lib


def register_service(settings):
    """Registra notif-svc en Consul con un healthcheck HTTP sobre /healthz."""
    c = consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)
    c.agent.service.register(
        name=settings.SERVICE_NAME,
        service_id=f"{settings.SERVICE_NAME}-1",
        address=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        check=consul_lib.Check.http(
            url=f"http://{settings.SERVICE_HOST}:{settings.SERVICE_PORT}/healthz",
            interval="10s",
            timeout="5s",
            deregister="30s",
        ),
    )


def deregister_service(settings):
    """Deregistra notif-svc de Consul (llamado en el shutdown del servicio)."""
    c = consul_lib.Consul(host=settings.CONSUL_HOST, port=settings.CONSUL_PORT)
    c.agent.service.deregister(service_id=f"{settings.SERVICE_NAME}-1")
