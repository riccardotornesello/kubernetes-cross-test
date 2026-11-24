from pydantic import Field

from resources.liqo import FirewallConfigurationResource
from resources.test.base import TestResource, TestResourceOptions
from validation import Dns1123Label, IPv4AddressOrCidr


class TunnelFirewallRuleOptions(TestResourceOptions):
    """
    Options:
        allowed_destination_ips (list[str]): List of allowed destination IPs (or CIDRs).
        allowed_source_ips (list[str]): List of allowed source IPs (or CIDRs).
        allow_to_offloaded_pods_from (str): Allow traffic to the pods offloaded by this cluster.
        allow_established (bool): Whether to allow established connections. Defaults to True.
    """

    allowed_destination_ips: list[IPv4AddressOrCidr] = Field(default_factory=list)
    allowed_source_ips: list[IPv4AddressOrCidr] = Field(default_factory=list)
    allow_to_offloaded_pods_from: Dns1123Label | None = None
    allow_established: bool = True

    def referenced_clusters(self) -> list[str]:
        if self.allow_to_offloaded_pods_from is None:
            return []
        return [self.allow_to_offloaded_pods_from]


class TunnelFirewallRuleResource(TestResource, FirewallConfigurationResource):
    """
    FirewallConfiguration of the gateway dropping the traffic coming from the
    tunnel, but for the allowed destinations and sources.
    """

    Options = TunnelFirewallRuleOptions
    options: TunnelFirewallRuleOptions

    def _get_body_content(self) -> dict:
        # Settings
        table_name = f"tunnel-firewall-table-{self.name}"

        allowed_destination_ips = list(self.options.allowed_destination_ips)
        allowed_source_ips = list(self.options.allowed_source_ips)
        allow_established = self.options.allow_established

        # Add allowed IPs for offloaded pods
        origin = self.options.allow_to_offloaded_pods_from
        if origin:
            for pod in self.cluster.offloaded_pods_from(origin):
                if pod.ip and pod.ip not in allowed_destination_ips:
                    allowed_destination_ips.append(pod.ip)

        # Rules
        accept_destination_rules = [
            {
                "action": "accept",
                "match": [
                    {
                        "ip": {
                            "position": "dst",
                            "value": ip,
                        },
                        "op": "eq",
                    },
                ],
            }
            for ip in allowed_destination_ips
        ]

        accept_source_rules = [
            {
                "action": "accept",
                "match": [
                    {
                        "ip": {
                            "position": "src",
                            "value": ip,
                        },
                        "op": "eq",
                    },
                ],
            }
            for ip in allowed_source_ips
        ]

        established_rule = {
            "action": "accept",
            "match": [
                {
                    "ctstate": {
                        "value": [
                            "established",
                            "related",
                        ],
                    },
                    "op": "eq",
                },
            ],
        }

        # Body
        return {
            "apiVersion": "networking.liqo.io/v1beta1",
            "kind": "FirewallConfiguration",
            "metadata": {
                "labels": {
                    "liqo.io/managed": "true",
                    "networking.liqo.io/firewall-category": "gateway",
                    "networking.liqo.io/firewall-subcategory": "fabric",
                }
            },
            "spec": {
                "table": {
                    "family": "IPV4",
                    "name": table_name,
                    "chains": [
                        {
                            "hook": "postrouting",
                            "name": "tunnel-firewall-chain",
                            "policy": "drop",
                            "priority": 200,
                            "type": "filter",
                            "rules": {
                                "filterRules": [
                                    # Consider only traffic coming from the wireguard tunnel to the geneve tunnels
                                    {
                                        "action": "accept",
                                        "match": [
                                            {
                                                "dev": {
                                                    "position": "in",
                                                    "value": "liqo-tunnel",
                                                },
                                                "op": "neq",
                                            },
                                        ],
                                    },
                                    {
                                        "action": "accept",
                                        "match": [
                                            {
                                                "dev": {
                                                    "position": "out",
                                                    "value": "eth0",
                                                },
                                                "op": "eq",
                                            },
                                        ],
                                    },
                                    # Accept allowed rules
                                    *([established_rule] if allow_established else []),
                                    *accept_destination_rules,
                                    *accept_source_rules,
                                ]
                            },
                        }
                    ],
                }
            },
        }
