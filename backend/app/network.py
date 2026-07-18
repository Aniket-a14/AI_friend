from ipaddress import ip_address


def _normalize_host(host: str | None) -> str | None:
    if not host:
        return None

    host = host.strip().lower()
    if "," in host:
        host = host.split(",", 1)[0].strip()
    if host == "127.0.0.1" or host == "::1":
        return host
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    elif ":" in host and host.count(":") == 1:
        host = host.rsplit(":", 1)[0]
    return host


def is_lan_client_allowed(host: str | None) -> bool:
    """Return true for loopback, private, and link-local clients."""
    host = _normalize_host(host)
    if not host:
        return False
    if host in ("127.0.0.1", "::1"):
        return True

    try:
        addr = ip_address(host)
    except ValueError:
        return False

    return addr.is_loopback or addr.is_private or addr.is_link_local


def is_loopback_client(host: str | None) -> bool:
    """Return true only for the host running the backend itself.

    Narrower than is_lan_client_allowed (which also trusts every other device
    on the LAN). Used to decide who gets a free pass on session auth (C1) -
    same-machine callers, not "anyone on the WiFi."
    """
    host = _normalize_host(host)
    if not host:
        return False
    if host in ("127.0.0.1", "::1"):
        return True

    try:
        addr = ip_address(host)
    except ValueError:
        return False

    return addr.is_loopback
