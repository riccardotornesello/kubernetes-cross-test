from resources.liqo import FirewallConfigurationResource
from resources.test.base import TestResource


class FabricFirewallRuleResource(TestResource, FirewallConfigurationResource):
    """
    FirewallConfiguration of the fabric dropping the traffic towards the
    Google public DNS servers. No options.
    """

    def _get_body_content(self) -> dict:
        return {
            "apiVersion": "networking.liqo.io/v1beta1",
            "kind": "FirewallConfiguration",
            "metadata": {
                "labels": {
                    "liqo.io/managed": "true",
                    "networking.liqo.io/firewall-category": "fabric",
                    "networking.liqo.io/firewall-subcategory": "all-nodes",
                }
            },
            "spec": {
                "table": {
                    "family": "IPV4",
                    "name": "fabric-firewall-table",
                    "chains": [
                        {
                            "hook": "prerouting",
                            "name": "fabric-firewall-chain",
                            "policy": "accept",
                            "priority": 99,
                            "type": "filter",
                            "rules": {
                                "filterRules": [
                                    {
                                        "action": "drop",
                                        "match": [
                                            {
                                                "ip": {
                                                    "value": "8.8.8.8,8.8.4.4",
                                                    "position": "dst",
                                                },
                                                "op": "eq",
                                            },
                                        ],
                                    }
                                ]
                            },
                        }
                    ],
                }
            },
        }
