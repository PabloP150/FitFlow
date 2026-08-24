from typing import Optional

import httpx

from .discovery import get_service_url


async def send_notification(
    user_id: int,
    notif_type: str,
    message: str,
    booking_id: Optional[int] = None,
):
    """Send a notification to notif-svc.

    Best-effort / fire-and-forget: resolves notif-svc via Consul discovery at
    call time (not at startup) so it can recover if notif-svc was briefly
    unavailable. Never raises — a failure here must not block a booking.
    """
    try:
        url = get_service_url("notif-svc")
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{url}/notifications",
                json={
                    "user_id": user_id,
                    "type": notif_type,
                    "message": message,
                    "booking_id": booking_id,
                },
                timeout=5,
            )
    except Exception as e:
        print(f"[notif_client] Failed to send notification: {e}")
        # Don't raise — this is a best-effort operation
