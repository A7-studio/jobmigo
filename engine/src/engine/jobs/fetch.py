"""Read a public job page like a polite visitor, and never reach a private network.

Every rule below is a refusal with a stable code (see `ApiError`):

* only http and https, no credentials in the address, only ports 80 and 443;
* the host is resolved once and every address must be public; the connection then goes
  to that validated address (the original host stays in `Host` and in the TLS name), so
  a name cannot change address between the check and the connection;
* every redirect hop is checked the same way (at most 3), and robots.txt is read for
  each hop before its page, and permission is never assumed when it cannot be read;
* no cookies, no proxies from the environment, no authorization header;
* the body is streamed and stopped at 1 MiB; the whole fetch has a 10 second limit;
* only `text/html` and `text/plain` with a 200 status are read.

Page text is untrusted: it goes through the same cleaner as a paste.
"""

import asyncio
import html
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import SplitResult, unquote, urljoin, urlsplit, urlunsplit

import httpx

from engine.errors import ApiError
from engine.jobs import robots
from engine.jobs.posting_guard import clean_posting

MAX_BYTES = 1_048_576
MAX_ROBOTS_BYTES = 524_288
MAX_REDIRECTS = 3
TOTAL_SECONDS = 10.0
MAX_URL_CHARS = 2000
MAX_TEXT_CHARS = 30_000
USER_AGENT = "JobmigoBot/1.0 (+https://usejobmigo.com)"

Resolver = Callable[[str, int], Awaitable[list[str]]]

_REDIRECTS = {301, 302, 303, 307, 308}
_NON_PUBLIC_V6 = tuple(
    ipaddress.ip_network(net)
    for net in ("64:ff9b::/96", "2002::/16", "fec0::/10", "::/96")
)  # NAT64, 6to4, site-local and IPv4-compatible forms (some count as global in Python)


def _blocked(message: str = "That address cannot be read.") -> ApiError:
    return ApiError(422, "fetch_blocked", message)


def _invalid() -> ApiError:
    return ApiError(422, "validation_failed", "The data is not valid.")


def _failed() -> ApiError:
    return ApiError(502, "fetch_failed", "The page could not be reached.")


def is_public(address: str) -> bool:
    """True only for a globally routable unicast address.

    Python counts multicast as global, and treats a 6to4 or NAT64 address as global even
    when it embeds a private IPv4 address, so those are refused here.
    """
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    if not ip.is_global or ip.is_multicast:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped is not None:
            return False
        if any(ip in net for net in _NON_PUBLIC_V6):
            return False
    return True


def parse_url(url: str) -> SplitResult:
    """The address split into parts, or a refusal."""
    if not url or len(url) > MAX_URL_CHARS or url != url.strip():
        raise _invalid()
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise _invalid() from None
    if parts.scheme.lower() not in ("http", "https") or not parts.hostname:
        raise _invalid()
    try:
        parts.hostname.encode("idna")
    except UnicodeError:
        raise _invalid() from None  # an empty or over-long label
    if parts.username is not None or parts.password is not None:
        raise _invalid()
    if port not in (None, 80, 443):
        raise _blocked("Only the standard web ports can be read.")
    return parts


async def system_resolver(host: str, port: int) -> list[str]:
    """The addresses of `host`, from the system resolver."""
    loop = asyncio.get_running_loop()
    try:
        found = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise _failed() from None
    return sorted({str(item[4][0]) for item in found})


async def _pin(parts: SplitResult, resolver: Resolver) -> str:
    """One validated public address for the host; all it resolves to must be public."""
    host = parts.hostname or ""
    port = parts.port or (443 if parts.scheme.lower() == "https" else 80)
    addresses = [host] if _is_literal(host) else await resolver(host, port)
    if not addresses:
        raise _failed()
    if not all(is_public(address) for address in addresses):
        raise _blocked()
    return addresses[0]


def _is_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


@dataclass
class _Response:
    status: int
    headers: httpx.Headers
    body: bytes


async def _get(
    client: httpx.AsyncClient,
    url: str,
    resolver: Resolver,
    *,
    limit: int,
    accept: str,
) -> _Response:
    """One request to a validated address. Never follows a redirect."""
    parts = parse_url(url)
    address = await _pin(parts, resolver)
    literal = f"[{address}]" if ":" in address else address
    port = f":{parts.port}" if parts.port else ""
    target = urlunsplit(
        (parts.scheme.lower(), literal + port, parts.path or "/", parts.query, "")
    )
    ascii_host = (parts.hostname or "").encode("idna").decode("ascii")
    host_header = (f"[{ascii_host}]" if ":" in ascii_host else ascii_host) + port
    headers = {
        "Host": host_header,
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "identity",  # no decompression, so no inflation past the cap
    }
    extensions = {"sni_hostname": ascii_host}
    try:
        async with client.stream(
            "GET", target, headers=headers, extensions=extensions
        ) as response:
            encoding = response.headers.get("content-encoding", "identity").lower()
            if encoding not in ("", "identity"):
                raise ApiError(422, "not_a_page", "That page could not be read.")
            data = bytearray()
            if response.status_code == 200:
                async for chunk in response.aiter_bytes():
                    data += chunk
                    if len(data) > limit:
                        raise ApiError(422, "too_large", "That page is too large.")
            return _Response(response.status_code, response.headers, bytes(data))
    except (httpx.HTTPError, UnicodeError, OSError):
        raise _failed() from None


async def _robots_ok(
    client: httpx.AsyncClient, parts: SplitResult, resolver: Resolver
) -> None:
    """Refuse unless robots.txt for this origin allows the path."""
    unreadable = ApiError(
        422, "robots_unreadable", "That site's rules could not be read."
    )
    current = urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), "/robots.txt", "", "")
    )
    response: _Response | None = None
    for _ in range(MAX_REDIRECTS + 1):
        try:
            found = await _get(
                client,
                current,
                resolver,
                limit=MAX_ROBOTS_BYTES,
                accept="text/plain,*/*",
            )
        except ApiError as error:
            if error.code in ("too_large", "not_a_page"):
                raise unreadable from None
            raise
        location = found.headers.get("location")
        if found.status in _REDIRECTS and location:
            current = _redirect_target(current, location)
            continue
        response = found
        break
    if response is None:
        raise unreadable
    if response.status == 404:
        return  # no published rules is permission
    if response.status != 200:
        raise unreadable
    text = response.body.decode("utf-8", errors="replace")
    if not robots.is_robots_body(text) or robots.has_undecodable_rule(text):
        raise unreadable
    # The rules are percent-decoded when matched, so the path and query are decoded too.
    path = unquote(parts.path or "/") + (
        f"?{unquote(parts.query)}" if parts.query else ""
    )
    try:
        permitted = robots.permits(text, path)
    except robots.RobotsTooComplex:
        raise unreadable from None
    if not permitted:
        raise ApiError(422, "robots_disallowed", "That site asks not to be read.")


def _redirect_target(current: str, location: str) -> str:
    """Where a redirect leads; a hop that is not a readable address is blocked."""
    target = urljoin(current, location)
    try:
        parse_url(target)
    except ApiError:
        raise _blocked("That link redirects somewhere it cannot go.") from None
    return target


def _decode(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    for part in content_type.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        if key.lower() == "charset" and value:
            charset = value.strip("\"' ").lower()
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _title(markup: str) -> str | None:
    """The page title, found with plain string search (no regex over the whole page)."""
    lower = markup.lower()
    start = lower.find("<title")
    if start < 0:
        return None
    begin = lower.find(">", start)
    end = lower.find("</title", begin + 1) if begin >= 0 else -1
    if begin < 0 or end < 0:
        return None
    text = " ".join(html.unescape(markup[begin + 1 : end]).split())
    return text[:200] or None


@dataclass(frozen=True)
class Page:
    text: str
    title: str | None
    final_url: str
    truncated: bool


async def fetch_page(
    url: str,
    *,
    resolver: Resolver | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> Page:
    """Fetch, check and clean a public job page; refusals are `ApiError`s."""
    use_resolver = resolver or system_resolver
    try:
        async with asyncio.timeout(TOTAL_SECONDS):
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                trust_env=False,
                timeout=httpx.Timeout(TOTAL_SECONDS),
            ) as client:
                return await _fetch(client, url, use_resolver)
    except TimeoutError:
        raise _failed() from None


async def _fetch(client: httpx.AsyncClient, url: str, resolver: Resolver) -> Page:
    current = url
    for _hop in range(MAX_REDIRECTS + 1):
        await _robots_ok(client, parse_url(current), resolver)
        response = await _get(
            client, current, resolver, limit=MAX_BYTES, accept="text/html,text/plain"
        )
        location = response.headers.get("location")
        if response.status in _REDIRECTS and location:
            current = _redirect_target(current, location)
            continue
        if response.status != 200:
            raise ApiError(422, "not_a_page", "That page could not be read.")
        content_type = response.headers.get("content-type", "")
        if content_type.split(";")[0].strip().lower() not in (
            "text/html",
            "text/plain",
        ):
            raise ApiError(422, "not_a_page", "That is not a web page.")
        markup = _decode(response.body, content_type)
        text, _counts = clean_posting(markup)
        truncated = len(text) > MAX_TEXT_CHARS
        return Page(
            text=text[:MAX_TEXT_CHARS],
            title=_title(markup),
            final_url=current,
            truncated=truncated,
        )
    raise _blocked("That link redirects too many times.")
