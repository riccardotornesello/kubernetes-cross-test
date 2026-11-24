"""Field types and helpers shared by the configuration models."""

import ipaddress
import re
from typing import Annotated, Any

from pydantic import AfterValidator, BeforeValidator

# RFC 1123 label (clusters, namespaces): the rule applied by the API server
_DNS1123_LABEL = re.compile(r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?$")
# ANSI SGR parameters, e.g. "44" or "1;44"
_ANSI_SGR = re.compile(r"^\d{1,3}(;\d{1,3})*$")


def _validate_dns1123_label(value: str) -> str:
    if len(value) > 63 or not _DNS1123_LABEL.match(value):
        raise ValueError(
            f"'{value}' is not a valid RFC 1123 label: at most 63 lowercase "
            "alphanumeric characters or '-', starting and ending with an "
            "alphanumeric character"
        )
    return value


def _validate_dns1123_subdomain(value: str) -> str:
    if len(value) > 253 or not all(
        _DNS1123_LABEL.match(part) for part in value.split(".")
    ):
        raise ValueError(
            f"'{value}' is not a valid RFC 1123 subdomain: at most 253 "
            "lowercase alphanumeric characters, '-' or '.', starting and "
            "ending with an alphanumeric character"
        )
    return value


def _validate_ipv4_cidr(value: str) -> str:
    try:
        return str(ipaddress.IPv4Network(value, strict=True))
    except ValueError as e:
        raise ValueError(f"invalid IPv4 CIDR '{value}': {e}") from e


def _validate_ipv4_address_or_cidr(value: str) -> str:
    try:
        if "/" in value:
            return str(ipaddress.IPv4Network(value, strict=True))
        return str(ipaddress.IPv4Address(value))
    except ValueError as e:
        raise ValueError(f"invalid IPv4 address or CIDR '{value}': {e}") from e


def _validate_ansi_color(value: str) -> str:
    if not _ANSI_SGR.match(value):
        raise ValueError(
            f"'{value}' is not a valid ANSI color code (e.g. '44' or '1;44')"
        )
    return value


def _to_str(value: Any) -> Any:
    # `color: 44` (an int in YAML) is the same as `color: "44"`
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else value


Dns1123Label = Annotated[str, AfterValidator(_validate_dns1123_label)]
Dns1123Subdomain = Annotated[str, AfterValidator(_validate_dns1123_subdomain)]
IPv4Cidr = Annotated[str, AfterValidator(_validate_ipv4_cidr)]
IPv4AddressOrCidr = Annotated[str, AfterValidator(_validate_ipv4_address_or_cidr)]
AnsiColor = Annotated[
    str, BeforeValidator(_to_str), AfterValidator(_validate_ansi_color)
]


def ensure_unique(names: list[str], what: str) -> None:
    """
    Raises if a name appears twice in `names`.

    Raises:
        ValueError: On the first duplicate, with its position.
    """
    seen = set()
    for i, name in enumerate(names):
        if name in seen:
            raise ValueError(f"duplicate {what} '{name}' (at {i})")
        seen.add(name)
