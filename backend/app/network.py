from ipaddress import ip_address


def is_lan_client_allowed(host: str | None) -> bool:
    """Return true for loopback, private, and link-local clients."""
    if not host:
        return False

    host = host.strip().lower()
    if "," in host:
        host = host.split(",", 1)[0].strip()
    if host == "127.0.0.1" or host == "::1":
        return True
    if host.startswith("[") and "]" in host:
        host = host[1 : host.index("]")]
    elif ":" in host and host.count(":") == 1:
        host = host.rsplit(":", 1)[0]

    try:
        addr = ip_address(host)
    except ValueError:
        return False

    return addr.is_loopback or addr.is_private or addr.is_link_local
