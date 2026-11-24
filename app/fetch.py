"""HTTPS with pinned public IP, TLS hostname verification and same-origin redirects."""
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import urlsplit, urljoin, urlunsplit, quote
from urllib.robotparser import RobotFileParser

AGENT = "DidbanKhedmat"
LIMIT = 2_000_000

def canonical(url):
    p = urlsplit(url)
    if p.scheme != "https" or not p.hostname or p.username or p.password or p.port not in (None,443):
        raise ValueError("A public HTTPS URL on port 443 is required")
    host = p.hostname.encode("idna").decode("ascii").lower()
    if ":" in host or any(ord(c)<33 for c in url):
        raise ValueError("Unsupported URL")
    return urlunsplit(("https", host, quote(p.path or "/", safe="/%:@-._~"), quote(p.query, safe="=&%+/:?"), ""))

def request(url):
    p = urlsplit(canonical(url))
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global or ipaddress.ip_address(a[4][0]).is_multicast for a in addresses):
        raise ValueError("Non-public destination")
    context = ssl.create_default_context()
    ips = list(dict.fromkeys(a[4][0] for a in addresses))
    # A host with only one address still gets a retry after a transient timeout.
    deadline = time.monotonic() + 45
    for ip in ips if len(ips) > 1 else ips * 2:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(f"Connection to {p.hostname} timed out")
        try:
            with socket.create_connection((ip,443), timeout=min(10, remaining)) as raw:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Connection to {p.hostname} timed out")
                raw.settimeout(min(20, remaining))
                secure = context.wrap_socket(raw, server_hostname=p.hostname)
            break
        except (PermissionError, ssl.SSLError):
            raise
        except OSError as exc:
            last_error = exc
    else:
        raise last_error
    conn = http.client.HTTPSConnection(p.hostname, timeout=10, context=context)
    try:
        with secure:
            secure.settimeout(10)
            conn.sock = secure
            conn.request("GET", p.path + ("?"+p.query if p.query else ""), headers={"User-Agent": AGENT, "Accept-Encoding":"identity"})
            res = conn.getresponse()
            data = bytearray()
            started = time.monotonic()
            while len(data) <= LIMIT and time.monotonic()-started < 20:
                chunk = res.read1(65536)
                if not chunk:
                    return res.status, res.headers, bytes(data)
                data.extend(chunk)
            raise ValueError("Response exceeded limits")
    finally:
        conn.close()

def fetch(url):
    url = canonical(url)
    base = urlsplit(url).netloc
    robots_url = "https://"+base+"/robots.txt"
    for _ in range(5):
        status, headers, data = request(robots_url)
        if status not in (301,302,303,307,308):
            break
        robots_url = canonical(urljoin(robots_url, headers["Location"]))
        if urlsplit(robots_url).netloc != base:
            raise ValueError("Cross-origin robots redirect")
    else:
        raise ValueError("Too many robots redirects")
    rules = RobotFileParser()
    if status == 200:
        rules.parse(data.decode("utf-8-sig","replace").splitlines())
    elif status not in (404,410):
        raise ValueError("Robots policy unavailable")
    else:
        rules.parse([])
    delay = max(2, rules.crawl_delay(AGENT) or 0)
    rate = rules.request_rate(AGENT)
    if rate and rate.requests:
        delay = max(delay, rate.seconds / rate.requests)
    if delay > 60:
        raise ValueError("Source requires a longer crawl interval")
    for _ in range(4):
        if not rules.can_fetch(AGENT, url):
            raise ValueError("Disallowed by robots policy")
        time.sleep(delay)
        status, headers, data = request(url)
        if status in (301,302,303,307,308):
            url = canonical(urljoin(url,headers["Location"]))
            if urlsplit(url).netloc != base:
                raise ValueError("Cross-origin redirect")
            continue
        if status != 200 or headers.get_content_type() not in ("text/html","application/xhtml+xml"):
            raise ValueError(f"Unsupported response HTTP {status}")
        return data.decode(headers.get_content_charset() or "utf-8","replace")
    raise ValueError("Too many redirects")

