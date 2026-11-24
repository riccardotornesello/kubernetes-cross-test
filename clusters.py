from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from utils.kubernetes.nodes import Node, get_nodes
from utils.kubernetes.pods import Pod, get_pods, get_local_offloaded_pods
from utils.kubernetes.services import Service, get_services
from utils.kubernetes.remapped_cidrs import get_remapped_cidrs
from utils.network import remap_ip

if TYPE_CHECKING:
    from input import ClusterConfig, RootConfig

# Label of the virtual nodes created by Liqo
VIRTUAL_NODE_LABEL = ("liqo.io/type", "virtual-node")


class Cluster:
    """
    A Kubernetes cluster under test, with the state fetched from it.

    The state is empty until `fetch` is called: a cluster restored from an
    output file (`from_dict`) has only its configuration.

    Attributes:
        name (str): The name of the cluster.
        color (str | None): ANSI color code associated with the cluster.
        kubeconfig_location (str): Path to the kubeconfig file for cluster access.
        namespaces (list[str]): Namespaces whose pods and services are tested.
        nodes (list[Node]): Nodes of the cluster.
        pods (dict[str, list[Pod]]): Namespace -> pods. Only pods running on
            real (non-virtual) nodes.
        services (dict[str, list[Service]]): Namespace -> services.
        remapped_cidrs (dict[str, str]): Remote cluster -> its pod CIDR, as
            remapped in this cluster.
        local_offloaded_pods (dict[str, list[Pod]]): Origin cluster -> pods it
            offloaded to this cluster.
    """

    def __init__(
        self,
        name: str,
        kubeconfig_location: str,
        namespaces: list[str],
        color: str | None = None,
    ):
        self.name = name
        self.color = color
        self.kubeconfig_location = kubeconfig_location
        self.namespaces = list(namespaces)

        self.fetched = False
        self.nodes: list[Node] = []
        self.pods: dict[str, list[Pod]] = {ns: [] for ns in self.namespaces}
        self.services: dict[str, list[Service]] = {ns: [] for ns in self.namespaces}
        self.remapped_cidrs: dict[str, str] = {}
        self.local_offloaded_pods: dict[str, list[Pod]] = {}

    # Construction and serialization

    @classmethod
    def from_config(cls, config: ClusterConfig) -> Cluster:
        """Cluster of a validated configuration (not fetched)."""
        return cls(
            name=config.name,
            kubeconfig_location=config.kubeconfig_location,
            namespaces=config.namespace_names,
            color=config.color,
        )

    @classmethod
    def from_dict(cls, data: dict) -> Cluster:
        """Cluster saved with `to_dict` (not fetched)."""
        return cls(
            name=data["name"],
            kubeconfig_location=data["kubeconfig_location"],
            namespaces=data["namespaces"],
            color=data.get("color"),
        )

    def to_dict(self) -> dict:
        """Configuration of the cluster, as saved in the output file."""
        return {
            "name": self.name,
            "kubeconfig_location": self.kubeconfig_location,
            "namespaces": self.namespaces,
            "color": self.color,
        }

    def __repr__(self) -> str:
        return f"Cluster(name={self.name!r}, namespaces={self.namespaces!r})"

    # State

    def fetch(self) -> Cluster:
        """
        Fetches nodes, pods, services, offloaded pods and remapped CIDRs from
        the cluster, replacing the previous state.

        Returns:
            Cluster: The cluster itself.
        """
        self.nodes = get_nodes(self.kubeconfig_location)

        virtual_nodes = self.virtual_nodes
        self.pods = {
            ns: get_pods(
                self.kubeconfig_location, namespace=ns, excluded_nodes=virtual_nodes
            )
            for ns in self.namespaces
        }
        self.services = {
            ns: get_services(self.kubeconfig_location, namespace=ns)
            for ns in self.namespaces
        }
        self.local_offloaded_pods = get_local_offloaded_pods(self.kubeconfig_location)
        self.remapped_cidrs = get_remapped_cidrs(self.kubeconfig_location)

        self.fetched = True
        return self

    @property
    def virtual_nodes(self) -> list[str]:
        """Names of the Liqo virtual nodes."""
        key, value = VIRTUAL_NODE_LABEL
        return [node.name for node in self.nodes if node.labels.get(key) == value]

    def iter_pods(self) -> Iterator[Pod]:
        """Pods of the tested namespaces, in namespace order."""
        for ns in self.namespaces:
            yield from self.pods.get(ns, [])

    def iter_services(self) -> Iterator[Service]:
        """Services of the tested namespaces, in namespace order."""
        for ns in self.namespaces:
            yield from self.services.get(ns, [])

    def offloaded_pods_from(self, origin: str | Cluster) -> list[Pod]:
        """Pods offloaded to this cluster by `origin`."""
        return self.local_offloaded_pods.get(_name(origin), [])

    # Peering and addressing

    @property
    def peers(self) -> list[str]:
        """Clusters whose pods are reachable (have a remapped CIDR)."""
        return sorted(self.remapped_cidrs)

    def can_reach(self, other: str | Cluster) -> bool:
        """Whether the pods of `other` are reachable from this cluster."""
        other = _name(other)
        return other == self.name or other in self.remapped_cidrs

    def remapped_cidr(self, other: str | Cluster) -> str:
        """
        Pod CIDR of `other`, as remapped in this cluster.

        Raises:
            ValueError: If `other` is not peered with this cluster.
        """
        other = _name(other)
        try:
            return self.remapped_cidrs[other]
        except KeyError:
            peers = ", ".join(self.peers) or "none"
            raise ValueError(
                f"cluster '{self.name}' has no remapped pod CIDR for "
                f"'{other}' (peers: {peers})"
            ) from None

    def remap_ip(self, ip: str, owner: str | Cluster) -> str:
        """
        Address to use from this cluster to reach `ip`, a pod address of the
        cluster `owner`.

        Raises:
            ValueError: If `owner` is not peered with this cluster.
        """
        if _name(owner) == self.name:
            return ip
        return remap_ip(ip, self.remapped_cidr(owner))

    # Display

    def colorize(self, text: str) -> str:
        """`text` padded and highlighted with the cluster color."""
        if not self.color:
            return f" {text} "
        return f"\x1b[{self.color}m {text} \x1b[0m"


def _name(cluster: str | Cluster) -> str:
    return cluster.name if isinstance(cluster, Cluster) else cluster


def load_clusters(config: RootConfig, fetch: bool = True) -> dict[str, Cluster]:
    """
    Clusters of a validated configuration, keyed by name.

    Args:
        config (RootConfig): The validated configuration.
        fetch (bool, optional): Whether to fetch their state. Defaults to True.
    """
    clusters = {c.name: Cluster.from_config(c) for c in config.clusters}
    if fetch:
        for cluster in clusters.values():
            cluster.fetch()
    return clusters
