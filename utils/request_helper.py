import json
import asyncio
from typing import Optional
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.httputil import HTTPHeaders


class ConnectionException(Exception):
    ...


async def reqretry(
    client: AsyncHTTPClient,
    url: str,
    params: Optional[dict] = None,
    method: str = "GET",
    **kwargs,
) -> dict:
    assert method in ["GET", "POST"], f"invalid method: {method}"
    headers = {}
    headers = {"Connection": "close"}
    if params is None:
        params = {}
    assert isinstance(params, dict), f"params must be dict but {type(params)}"
    kwargs.update({"request_timeout": 0, "connect_timeout": 0})
    for idx in range(3):

        try:
            if method == "GET":
                payload = "&".join([f"{key}={value}" for key, value in params.items()])
                payload = payload if not len(payload) else ("?" + payload)
                fullurl = f"{url.strip('/')}{payload}"
                httpreq = HTTPRequest(url=fullurl, **kwargs)
            else:
                httpreq = HTTPRequest(
                    url=url, method="POST", body=json.dumps(params), **kwargs
                )
            httpreq.headers = HTTPHeaders(headers)
            res = await client.fetch(httpreq)
        except Exception as e:
            print(
                f"req_{method} failed({idx+1}): {str(e)}, retry after 1s, url: {url}, params: {params}"
            )
            await asyncio.sleep(1)
            continue

        assert (
            res.code == 200
        ), f"response status_code: {res.code}, msg: {res.body.decode()}"
        resp = json.loads(res.body.decode())
        assert resp["error"] == "", f"response error: {resp['error']}"
        assert resp["code"] == 200, f"response code: {resp['code']}"
        return resp

    raise ConnectionException("req failed")
