import httpx
from .discovery import get_service_url
from typing import Optional


async def get_available_classes() -> list[dict]:
    """Get available fitness classes from booking-svc"""
    try:
        url = get_service_url("booking-svc")
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/classes", timeout=10)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}


async def _login(email: str, password: str) -> str:
    """Helper: login to users-svc and return JWT token"""
    try:
        url = get_service_url("users-svc")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/users/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
            return data["access_token"]
    except Exception as e:
        raise Exception(f"Login failed: {e}")


async def create_booking(class_id: int, email: str, password: str) -> dict:
    """Create a booking for a fitness class"""
    try:
        # 1. Login
        token = await _login(email, password)

        # 2. Create booking
        url = get_service_url("booking-svc")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/bookings",
                json={"class_id": class_id},
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}


async def cancel_booking(booking_id: int, email: str, password: str) -> dict:
    """Cancel a booking"""
    try:
        # 1. Login
        token = await _login(email, password)

        # 2. Cancel booking
        url = get_service_url("booking-svc")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/bookings/{booking_id}/cancel",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}


async def send_notification(
    user_id: int,
    type: str,
    message: str,
    booking_id: Optional[int] = None,
) -> dict:
    """Send a notification to a user via notif-svc.

    Trafico servicio-a-servicio: `POST /notifications` no lleva JWT (mismo
    payload que booking-svc/app/notif_client.py).
    """
    try:
        url = get_service_url("notif-svc")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{url}/notifications",
                json={
                    "user_id": user_id,
                    "type": type,
                    "message": message,
                    "booking_id": booking_id,
                },
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}


async def get_notification_history(user_id: int, email: str, password: str) -> list[dict]:
    """Get a user's notification history from notif-svc.

    Requiere JWT propio: notif-svc verifica ownership (403 si el token es de
    otro usuario), asi que el email/password deben ser los del `user_id` pedido.
    """
    try:
        # 1. Login
        token = await _login(email, password)

        # 2. Get history
        url = get_service_url("notif-svc")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{url}/notifications/user/{user_id}",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        return {"error": str(e)}
