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
