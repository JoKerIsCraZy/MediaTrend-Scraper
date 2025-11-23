import aiohttp
import asyncio
from typing import Optional, Dict, Any
import utils.menu as menu

class AsyncClient:
    _session: Optional[aiohttp.ClientSession] = None

    @classmethod
    async def get_session(cls) -> aiohttp.ClientSession:
        if cls._session is None or cls._session.closed:
            cls._session = aiohttp.ClientSession()
        return cls._session

    @classmethod
    async def close(cls):
        if cls._session and not cls._session.closed:
            await cls._session.close()
            cls._session = None

    @classmethod
    async def get(cls, url: str, params: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Optional[Any]:
        session = await cls.get_session()
        try:
            async with session.get(url, params=params, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                # Try to parse JSON, fallback to text if needed, or just return None on failure
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()
        except Exception as e:
            # We log the error but don't crash
            # log_error(f"Request failed: {url} - {e}") # Optional: avoid circular imports if utils.menu uses something else
            print(f"Request failed: {url} - {e}")
            return None

    @classmethod
    async def post(cls, url: str, json_data: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None, timeout: int = 10) -> Optional[Any]:
        session = await cls.get_session()
        try:
            async with session.post(url, json=json_data, headers=headers, timeout=timeout) as response:
                response.raise_for_status()
                if "application/json" in response.headers.get("Content-Type", ""):
                    return await response.json()
                return await response.text()
        except Exception as e:
            print(f"POST Request failed: {url} - {e}")
            return None
