from resources import FirewallConfigurationResource


class FabricFirewallRuleResource(FirewallConfigurationResource):
    def __init__(
        self,
        kubeconfig_path: str,
        namespace: str,
        name: str,
    ):
        super().__init__(
            kubeconfig_path=kubeconfig_path,
            namespace=namespace,
            name=name,
        )
        
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
