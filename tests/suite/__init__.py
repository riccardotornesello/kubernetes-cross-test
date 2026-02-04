from .curl import test_curl
from .nslookup import test_nslookup
from .ping import test_ping

test_suite = {
    "curl": test_curl,
    "nslookup": test_nslookup,
    "ping": test_ping,
}
