from .base import TestResource, TestResourceOptions
from .fabric_firewall_rule import FabricFirewallRuleResource
from .isolation_network_policy import IsolationNetworkPolicyResource
from .tunnel_firewall_rule import TunnelFirewallRuleResource

# `type` of a resource in the configuration file -> resource class. The
# `options` of the resource are validated against the class `Options` model.
test_resources: dict[str, type[TestResource]] = {
    "fabric_firewall_rule": FabricFirewallRuleResource,
    "isolation_network_policy": IsolationNetworkPolicyResource,
    "tunnel_firewall_rule": TunnelFirewallRuleResource,
}

__all__ = ["TestResource", "TestResourceOptions", "test_resources"]
