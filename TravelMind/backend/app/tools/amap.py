"""AMap Web Service tools with compact, model-friendly results."""

import re
from datetime import UTC, datetime
from math import ceil
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field

from app.config import settings

AMAP_BASE_URL = "https://restapi.amap.com"
_COORDINATES = re.compile(r"^-?\d{1,3}(?:\.\d+)?,-?\d{1,2}(?:\.\d+)?$")


class AMapAPIError(RuntimeError):
    """A safe error that never includes the Web Service key."""


class GeocodeArgs(BaseModel):
    """Address lookup arguments."""

    address: str = Field(min_length=1, max_length=200)
    city: str | None = Field(default=None, max_length=50)


class SearchPOIArgs(BaseModel):
    """Point-of-interest search arguments."""

    keywords: str = Field(min_length=1, max_length=100)
    city: str = Field(min_length=1, max_length=50)
    page_size: int = Field(default=5, ge=1, le=10)


class RouteArgs(BaseModel):
    """Route planning arguments using addresses or ``longitude,latitude``."""

    origin: str = Field(min_length=1, max_length=200)
    destination: str = Field(min_length=1, max_length=200)
    city: str | None = Field(
        default=None,
        max_length=50,
        description="出发城市；起终点跨城时只用于解析出发地",
    )
    mode: Literal["walking", "driving", "transit"] = "transit"
    destination_city: str | None = Field(
        default=None,
        max_length=50,
        description="目的地城市；跨城路线建议填写",
    )


def _observed_at() -> str:
    return datetime.now(UTC).isoformat()


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _number(value: Any) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _is_coordinates(value: str) -> bool:
    if not _COORDINATES.fullmatch(value.strip()):
        return False
    longitude, latitude = (float(part) for part in value.split(","))
    return -180 <= longitude <= 180 and -90 <= latitude <= 90


async def _request(
    path: str,
    params: dict[str, Any],
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Call AMap and normalize transport/protocol failures without leaking keys."""
    key = api_key or (
        settings.amap_api_key.get_secret_value() if settings.amap_api_key else None
    )
    if not key:
        raise AMapAPIError("缺少 AMAP_API_KEY，无法调用高德地图")

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            base_url=AMAP_BASE_URL,
            timeout=settings.amap_timeout_seconds,
            follow_redirects=True,
        )
    try:
        response = await client.get(path, params={**params, "key": key})
        if response.status_code >= 500:
            raise ConnectionError("高德地图服务暂时不可用")
        if response.status_code >= 400:
            raise AMapAPIError(f"高德地图返回 HTTP {response.status_code}")
        payload = response.json()
    except httpx.TimeoutException as error:
        raise TimeoutError("高德地图请求超时") from error
    except httpx.RequestError as error:
        raise ConnectionError("无法连接高德地图服务") from error
    except ValueError as error:
        raise AMapAPIError("高德地图返回了无效 JSON") from error
    finally:
        if owns_client:
            await client.aclose()

    if not isinstance(payload, dict) or payload.get("status") != "1":
        info = payload.get("info", "UNKNOWN") if isinstance(payload, dict) else "UNKNOWN"
        code = payload.get("infocode", "") if isinstance(payload, dict) else ""
        raise AMapAPIError(f"高德地图调用失败：{info} {code}".strip())
    return payload


async def geocode(
    address: str,
    city: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Convert one Chinese address or place name into coordinates."""
    params: dict[str, Any] = {"address": address, "output": "JSON"}
    if city:
        params["city"] = city
    payload = await _request(
        "/v3/geocode/geo",
        params,
        client=client,
        api_key=api_key,
    )
    rows = payload.get("geocodes") or []
    if not rows:
        raise AMapAPIError(f"高德地图未找到地点：{address}")
    row = rows[0]
    location = _text(row.get("location"))
    if location is None:
        raise AMapAPIError(f"高德地图没有返回地点坐标：{address}")
    return {
        "formatted_address": _text(row.get("formatted_address")) or address,
        "location": location,
        "province": _text(row.get("province")),
        "city": _text(row.get("city")),
        "district": _text(row.get("district")),
        "adcode": _text(row.get("adcode")),
        "citycode": _text(row.get("citycode")),
        "level": _text(row.get("level")),
        "source": "amap.geocode",
        "observed_at": _observed_at(),
    }


async def search_poi(
    keywords: str,
    city: str,
    page_size: int = 5,
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Search real AMap points of interest in one city."""
    payload = await _request(
        "/v5/place/text",
        {
            "keywords": keywords,
            "region": city,
            "city_limit": "true",
            "page_size": page_size,
            "show_fields": "business",
        },
        client=client,
        api_key=api_key,
    )
    pois = [
        {
            "id": _text(row.get("id")),
            "name": _text(row.get("name")),
            "address": _text(row.get("address")),
            "location": _text(row.get("location")),
            "type": _text(row.get("type")),
            "distance_m": _number(row.get("distance")),
        }
        for row in (payload.get("pois") or [])[:page_size]
    ]
    return {
        "keywords": keywords,
        "city": city,
        "pois": pois,
        "source": "amap.poi",
        "observed_at": _observed_at(),
    }


async def _resolve_place(
    value: str,
    city: str | None,
    *,
    client: httpx.AsyncClient,
    api_key: str | None,
) -> dict[str, Any]:
    if _is_coordinates(value):
        return {"formatted_address": value, "location": value, "city": city}
    return await geocode(value, city, client=client, api_key=api_key)


def _instructions(path: dict[str, Any]) -> list[str]:
    return [
        instruction
        for step in (path.get("steps") or [])[:10]
        if (instruction := _text(step.get("instruction")))
    ]


def _transit_segments(transit: dict[str, Any]) -> list[dict[str, Any]]:
    segments: list[dict[str, Any]] = []
    for segment in (transit.get("segments") or [])[:10]:
        buslines = (segment.get("bus") or {}).get("buslines") or []
        segments.append(
            {
                "walking_distance_m": _number((segment.get("walking") or {}).get("distance")),
                "bus_lines": [
                    {
                        "name": _text(line.get("name")),
                        "departure_stop": _text((line.get("departure_stop") or {}).get("name")),
                        "arrival_stop": _text((line.get("arrival_stop") or {}).get("name")),
                        "duration_minutes": (
                            ceil(duration / 60)
                            if (duration := _number(line.get("duration"))) is not None
                            else None
                        ),
                    }
                    for line in buslines[:3]
                ],
            }
        )
    return segments


async def plan_route(
    origin: str,
    destination: str,
    city: str | None = None,
    mode: Literal["walking", "driving", "transit"] = "transit",
    destination_city: str | None = None,
    *,
    client: httpx.AsyncClient | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    """Resolve two places and return one compact real route."""
    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(
            base_url=AMAP_BASE_URL,
            timeout=settings.amap_timeout_seconds,
            follow_redirects=True,
        )
    try:
        origin_place = await _resolve_place(origin, city, client=client, api_key=api_key)
        try:
            destination_place = await _resolve_place(
                destination,
                destination_city or city,
                client=client,
                api_key=api_key,
            )
        except AMapAPIError as error:
            can_retry_without_city = (
                destination_city is None
                and city is not None
                and ("30001" in str(error) or "未找到地点" in str(error))
            )
            if not can_retry_without_city:
                raise
            destination_place = await _resolve_place(
                destination,
                None,
                client=client,
                api_key=api_key,
            )
        params: dict[str, Any] = {
            "origin": origin_place["location"],
            "destination": destination_place["location"],
            "output": "JSON",
        }
        if mode == "transit":
            origin_city = city or origin_place.get("citycode") or origin_place.get("city")
            if not origin_city:
                raise AMapAPIError("公交路线必须提供 city，或使用可识别的中文出发地")
            params["city"] = origin_city
            destination_route_city = (
                destination_city
                or destination_place.get("citycode")
                or destination_place.get("city")
            )
            if destination_route_city:
                params["cityd"] = destination_route_city
            params["strategy"] = 3
            path = "/v3/direction/transit/integrated"
        else:
            path = f"/v3/direction/{mode}"
        payload = await _request(path, params, client=client, api_key=api_key)
    finally:
        if owns_client:
            await client.aclose()

    route = payload.get("route") or {}
    if mode == "transit":
        rows = route.get("transits") or []
        if not rows:
            raise AMapAPIError("高德地图未找到公交路线")
        selected = rows[0]
        result = {
            "duration_minutes": (
                ceil(duration / 60)
                if (duration := _number(selected.get("duration"))) is not None
                else None
            ),
            "walking_distance_m": _number(selected.get("walking_distance")),
            "cost": _text(selected.get("cost")),
            "segments": _transit_segments(selected),
        }
    else:
        rows = route.get("paths") or []
        if not rows:
            raise AMapAPIError(f"高德地图未找到{mode}路线")
        selected = rows[0]
        result = {
            "distance_m": _number(selected.get("distance")),
            "duration_minutes": (
                ceil(duration / 60)
                if (duration := _number(selected.get("duration"))) is not None
                else None
            ),
            "instructions": _instructions(selected),
        }

    return {
        "mode": mode,
        "origin": origin_place,
        "destination": destination_place,
        **result,
        "source": "amap.route",
        "observed_at": _observed_at(),
    }


async def static_map_image(locations: list[str]) -> bytes:
    """Render geocoded markers through AMap without exposing the Web key."""
    if not locations:
        raise AMapAPIError("地图至少需要一个坐标")
    key = settings.amap_api_key.get_secret_value() if settings.amap_api_key else None
    if not key:
        raise AMapAPIError("缺少 AMAP_API_KEY，无法生成地图")
    markers = "|".join(
        f"mid,,{chr(65 + index)}:{location}"
        for index, location in enumerate(locations[:20])
    )
    try:
        async with httpx.AsyncClient(
            base_url=AMAP_BASE_URL,
            timeout=settings.amap_timeout_seconds,
        ) as client:
            response = await client.get(
                "/v3/staticmap",
                params={"size": "750*400", "markers": markers, "key": key},
            )
            response.raise_for_status()
    except httpx.TimeoutException as error:
        raise TimeoutError("高德静态地图请求超时") from error
    except httpx.HTTPError as error:
        raise AMapAPIError("高德静态地图生成失败") from error
    if not response.headers.get("content-type", "").startswith("image/"):
        raise AMapAPIError("高德静态地图没有返回图片")
    return response.content
