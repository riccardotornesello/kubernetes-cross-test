from pydantic import Field

from resources.kubernetes import NetworkPolicyResource
from resources.test.base import TestResource, TestResourceOptions
from validation import Dns1123Label, IPv4Cidr


class IsolationNetworkPolicyOptions(TestResourceOptions):
    """
    Options:
        allowed_cidrs (list[str]): List of allowed CIDR blocks.
        allowed_namespaces (list[str]): List of allowed namespaces.
        allowed_clusters (list[str]): List of allowed (remote) clusters.
    """

    allowed_cidrs: list[IPv4Cidr] = Field(default_factory=list)
    allowed_namespaces: list[Dns1123Label] = Field(default_factory=list)
    allowed_clusters: list[Dns1123Label] = Field(default_factory=list)

    def referenced_clusters(self) -> list[str]:
        return list(self.allowed_clusters)


class IsolationNetworkPolicyResource(TestResource, NetworkPolicyResource):
    """
    NetworkPolicy isolating the pods of a namespace: only traffic within the
    namespace, with the allowed namespaces, CIDRs and clusters, and towards
    public addresses is allowed.
    """

    Options = IsolationNetworkPolicyOptions
    options: IsolationNetworkPolicyOptions

    def _get_body_content(self) -> dict:
        # Remapped pod CIDRs of the allowed clusters, as seen from this cluster
        allowed_cluster_cidrs = [
            self.cluster.remapped_cidr(c) for c in self.options.allowed_clusters
        ]

        # Rules
        allowed_cidr_egress_rules = [
            {"to": [{"ipBlock": {"cidr": cidr}}]}
            for cidr in self.options.allowed_cidrs
        ]
        allowed_cidr_ingress_rules = [
            {"from": [{"ipBlock": {"cidr": cidr}}]}
            for cidr in self.options.allowed_cidrs
        ]

        allowed_namespaces_egress_rules = [
            {"to": [{"namespaceSelector": {"matchLabels": {"name": ns}}}]}
            for ns in self.options.allowed_namespaces
        ]
        allowed_namespaces_ingress_rules = [
            {"from": [{"namespaceSelector": {"matchLabels": {"name": ns}}}]}
            for ns in self.options.allowed_namespaces
        ]

        allowed_clusters_egress_rules = [
            {"to": [{"ipBlock": {"cidr": cidr}}]} for cidr in allowed_cluster_cidrs
        ]
        allowed_clusters_ingress_rules = [
            {"from": [{"ipBlock": {"cidr": cidr}}]} for cidr in allowed_cluster_cidrs
        ]

        # Body
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "spec": {
                "podSelector": {},
                "policyTypes": ["Egress", "Ingress"],
                "egress": [
                    # Allow traffic to pods in the same namespace
                    {"to": [{"podSelector": {}}]},
                    # Allow traffic to pods in allowed namespaces
                    *allowed_namespaces_egress_rules,
                    # Allow traffic to allowed CIDRs
                    *allowed_cidr_egress_rules,
                    # Allow traffic to allowed clusters
                    *allowed_clusters_egress_rules,
                    # Block traffic to other private IP ranges
                    {
                        "to": [
                            {
                                "ipBlock": {
                                    "cidr": "0.0.0.0/0",
                                    "except": [
                                        "10.0.0.0/8",
                                        "192.168.0.0/16",
                                        "172.16.0.0/20",
                                    ],
                                }
                            }
                        ]
                    },
                ],
                "ingress": [
                    # Allow traffic from pods in the same namespace
                    {"from": [{"podSelector": {}}]},
                    # Allow traffic from pods in allowed namespaces
                    *allowed_namespaces_ingress_rules,
                    # Allow traffic from allowed CIDRs
                    *allowed_cidr_ingress_rules,
                    # Allow traffic from allowed clusters
                    *allowed_clusters_ingress_rules,
                ],
            },
        }
