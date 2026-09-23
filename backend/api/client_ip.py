"""
Resolve the visitor's address behind the production proxies.

Railway's edge sets ``X-Real-IP`` to the peer that connected to it. Behind the
Cloudflare proxy that peer is a Cloudflare edge server, and ``CF-Connecting-IP``
carries the visitor's address. That header is trusted only when the peer lies
in Cloudflare's published ranges, so a request that bypasses Cloudflare cannot
choose its own rate-limit key.
"""
import ipaddress
import logging

import httpx
from starlette.requests import Request

from config.settings import settings

logger = logging.getLogger(__name__)

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address
IPNetwork = ipaddress.IPv4Network | ipaddress.IPv6Network

_cloudflare_networks: tuple[IPNetwork, ...] = ()


async def load_cloudflare_networks() -> None:
    """Fetch Cloudflare's edge ranges. On failure CF-Connecting-IP stays untrusted."""
    global _cloudflare_networks
    if not settings.cloudflare_ips_url:
        return
    try:
        async with httpx.AsyncClient(timeout=settings.cloudflare_ips_timeout_seconds) as http:
            response = await http.get(settings.cloudflare_ips_url)
            response.raise_for_status()
            result = response.json()["result"]
        _cloudflare_networks = tuple(
            ipaddress.ip_network(cidr) for cidr in [*result["ipv4_cidrs"], *result["ipv6_cidrs"]]
        )
        logger.info("Loaded %d Cloudflare edge ranges", len(_cloudflare_networks))
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
        logger.warning("Cloudflare edge ranges unavailable; CF-Connecting-IP is not trusted: %s", exc)


def _parse_address(value: str | None) -> IPAddress | None:
    if not value:
        return None
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def client_ip(request: Request) -> str:
    """Return the visitor's address, used as the rate-limit key and for telemetry."""
    peer = _parse_address(request.headers.get(settings.client_ip_header)) if settings.client_ip_header else None
    if peer is None:
        return request.client.host if request.client else "unknown"
    if any(peer in network for network in _cloudflare_networks):
        visitor = _parse_address(request.headers.get("CF-Connecting-IP"))
        if visitor is not None:
            return str(visitor)
    return str(peer)
