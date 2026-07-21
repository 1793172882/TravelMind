"""Contract tests for normalized AMap Web Service tools."""

from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from app.agent.runtime import build_default_registry
from app.config import settings
from app.tools.amap import geocode, plan_route, search_poi
from app.tools.weather import query_weather


def _response(request: httpx.Request) -> httpx.Response:
    params = parse_qs(request.url.query.decode())
    if request.url.path == "/v3/geocode/geo":
        address = params["address"][0]
        destination = "西湖" in address
        return httpx.Response(
            200,
            json={
                "status": "1",
                "geocodes": [
                    {
                        "formatted_address": address,
                        "location": "120.15,30.25" if destination else "120.10,30.20",
                        "province": "浙江省",
                        "city": "杭州市",
                        "district": "西湖区",
                        "adcode": "330106",
                        "citycode": "0571",
                        "level": "兴趣点",
                    }
                ],
            },
        )
    if request.url.path == "/v5/place/text":
        return httpx.Response(
            200,
            json={
                "status": "1",
                "pois": [
                    {
                        "id": "poi-1",
                        "name": "西湖风景名胜区",
                        "address": "龙井路1号",
                        "location": "120.15,30.25",
                        "type": "风景名胜",
                    }
                ],
            },
        )
    if request.url.path == "/v3/weather/weatherInfo":
        return httpx.Response(
            200,
            json={
                "status": "1",
                "forecasts": [
                    {
                        "province": "浙江",
                        "city": "杭州",
                        "reporttime": "2026-07-20 11:00:00",
                        "casts": [
                            {
                                "date": "2026-07-21",
                                "dayweather": "晴",
                                "nightweather": "多云",
                                "daytemp": "32",
                                "nighttemp": "25",
                                "daywind": "东",
                                "daypower": "≤3",
                            }
                        ],
                    }
                ],
            },
        )
    if request.url.path == "/v3/direction/transit/integrated":
        return httpx.Response(
            200,
            json={
                "status": "1",
                "route": {
                    "transits": [
                        {
                            "duration": "3600",
                            "walking_distance": "600",
                            "cost": "6.0",
                            "segments": [
                                {
                                    "walking": {"distance": "200"},
                                    "bus": {
                                        "buslines": [
                                            {
                                                "name": "地铁1号线",
                                                "departure_stop": {"name": "城站"},
                                                "arrival_stop": {"name": "龙翔桥"},
                                                "duration": "1200",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    ]
                },
            },
        )
    return httpx.Response(404)


@pytest.mark.anyio
async def test_amap_tools_normalize_real_api_shapes() -> None:
    async with httpx.AsyncClient(
        base_url="https://restapi.amap.com",
        transport=httpx.MockTransport(_response),
    ) as client:
        location = await geocode("杭州站", client=client, api_key="test-key")
        pois = await search_poi("西湖", "杭州", client=client, api_key="test-key")
        weather = await query_weather("杭州", client=client, api_key="test-key")
        route = await plan_route(
            "杭州站",
            "西湖",
            "杭州",
            "transit",
            client=client,
            api_key="test-key",
        )

    assert location["location"] == "120.10,30.20"
    assert pois["pois"][0]["name"] == "西湖风景名胜区"
    assert weather["casts"][0]["day_weather"] == "晴"
    assert route["duration_minutes"] == 60
    assert route["segments"][0]["bus_lines"][0]["name"] == "地铁1号线"


@pytest.mark.anyio
async def test_cross_city_route_retries_destination_without_origin_city() -> None:
    geocode_calls: list[tuple[str, str | None]] = []

    def response(request: httpx.Request) -> httpx.Response:
        params = parse_qs(request.url.query.decode())
        if request.url.path == "/v3/geocode/geo":
            address = params["address"][0]
            city = params.get("city", [None])[0]
            geocode_calls.append((address, city))
            if address == "杭州" and city == "上海":
                return httpx.Response(
                    200,
                    json={
                        "status": "0",
                        "info": "ENGINE_RESPONSE_DATA_ERROR",
                        "infocode": "30001",
                    },
                )
            is_hangzhou = address == "杭州"
            return httpx.Response(
                200,
                json={
                    "status": "1",
                    "geocodes": [
                        {
                            "formatted_address": address,
                            "location": "120.15,30.25" if is_hangzhou else "121.47,31.23",
                            "city": "杭州市" if is_hangzhou else "上海市",
                            "citycode": "0571" if is_hangzhou else "021",
                        }
                    ],
                },
            )
        return _response(request)

    async with httpx.AsyncClient(
        base_url="https://restapi.amap.com",
        transport=httpx.MockTransport(response),
    ) as client:
        route = await plan_route(
            "上海",
            "杭州",
            "上海",
            "transit",
            client=client,
            api_key="test-key",
        )

    assert geocode_calls == [("上海", "上海"), ("杭州", "上海"), ("杭州", None)]
    assert route["destination"]["city"] == "杭州市"
    assert route["duration_minutes"] == 60


def test_amap_tools_are_registered_only_when_key_exists(monkeypatch) -> None:
    monkeypatch.setattr(settings, "amap_api_key", None)
    without_key = {tool.name for tool in build_default_registry().list_tools()}
    monkeypatch.setattr(settings, "amap_api_key", SecretStr("test-key"))
    with_key = {tool.name for tool in build_default_registry().list_tools()}

    assert not any(name.startswith("amap.") for name in without_key)
    assert {
        "amap.geocode",
        "amap.search_poi",
        "amap.weather",
        "amap.plan_route",
    } <= with_key
