"""Visitor address resolution behind Railway's edge and the Cloudflare proxy."""
import ipaddress

import httpx
import pytest
from starlette.requests import Request

from api import client_ip as client_ip_module
from api.client_ip import client_ip, load_cloudflare_networks
from config.settings import settings

CLOUDFLARE_PEER = "173.245.48.10"
CLOUDFLARE_RANGES = {"ipv4_cidrs": ["173.245.48.0/20"], "ipv6_cidrs": ["2400:cb00::/32"]}


def make_request(headers: dict[str, str], peer: str = "100.64.0.2") -> Request:
    return Request({
        "type": "http",
        "headers": [(name.lower().encode(), value.encode()) for name, value in headers.items()],
        "client": (peer, 40000),
    })


@pytest.fixture
def cloudflare_ranges(monkeypatch):
    networks = tuple(ipaddress.ip_network(cidr) for cidrs in CLOUDFLARE_RANGES.values() for cidr in cidrs)
    monkeypatch.setattr(client_ip_module, "_cloudflare_networks", networks)


def test_socket_peer_is_used_without_the_edge_header():
    assert client_ip(make_request({}, peer="127.0.0.1")) == "127.0.0.1"


def test_edge_header_identifies_a_direct_visitor(cloudflare_ranges):
    request = make_request({"X-Real-IP": "203.0.113.7", "CF-Connecting-IP": "198.51.100.1"})
    assert client_ip(request) == "203.0.113.7"


def test_cloudflare_header_is_trusted_only_from_cloudflare_peers(cloudflare_ranges):
    request = make_request({"X-Real-IP": CLOUDFLARE_PEER, "CF-Connecting-IP": "198.51.100.1"})
    assert client_ip(request) == "198.51.100.1"


def test_cloudflare_ipv6_visitor(cloudflare_ranges):
    request = make_request({"X-Real-IP": "2400:cb00::1", "CF-Connecting-IP": "2001:db8::5"})
    assert client_ip(request) == "2001:db8::5"


def test_invalid_cloudflare_header_keeps_the_peer(cloudflare_ranges):
    request = make_request({"X-Real-IP": CLOUDFLARE_PEER, "CF-Connecting-IP": "not-an-ip"})
    assert client_ip(request) == CLOUDFLARE_PEER


def test_cloudflare_header_is_ignored_until_ranges_load(monkeypatch):
    monkeypatch.setattr(client_ip_module, "_cloudflare_networks", ())
    request = make_request({"X-Real-IP": CLOUDFLARE_PEER, "CF-Connecting-IP": "198.51.100.1"})
    assert client_ip(request) == CLOUDFLARE_PEER


def test_invalid_edge_header_falls_back_to_the_socket_peer():
    assert client_ip(make_request({"X-Real-IP": "garbage"}, peer="10.1.2.3")) == "10.1.2.3"


def _mock_http_client(monkeypatch, handler) -> None:
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        client_ip_module.httpx, "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(settings, "cloudflare_ips_url", "https://cloudflare.test/ips")
    monkeypatch.setattr(client_ip_module, "_cloudflare_networks", ())


@pytest.mark.asyncio
async def test_load_cloudflare_networks_parses_both_families(monkeypatch):
    _mock_http_client(monkeypatch, lambda request: httpx.Response(200, json={"result": CLOUDFLARE_RANGES}))
    await load_cloudflare_networks()
    assert [str(network) for network in client_ip_module._cloudflare_networks] == [
        "173.245.48.0/20", "2400:cb00::/32",
    ]


@pytest.mark.asyncio
async def test_failed_range_fetch_leaves_the_header_untrusted(monkeypatch, caplog):
    _mock_http_client(monkeypatch, lambda request: httpx.Response(503))
    await load_cloudflare_networks()
    assert client_ip_module._cloudflare_networks == ()
    assert "CF-Connecting-IP is not trusted" in caplog.text
