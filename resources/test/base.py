"""Base of the resources created by a test case."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict

from resources.base import BaseResource

if TYPE_CHECKING:
    from clusters import Cluster


class TestResourceOptions(BaseModel):
    """
    `options` of a test resource. Each resource type defines its own subclass,
    validated when the configuration file is loaded.
    """

    model_config = ConfigDict(extra="forbid")

    def referenced_clusters(self) -> list[str]:
        """Names of the (remote) clusters the options refer to."""
        return []

    def validate_clusters(self, cluster: str, known_clusters: list[str]) -> None:
        """
        Checks the clusters the options refer to: they must be known and
        differ from `cluster`, the one the resource is created in.

        Raises:
            ValueError: If a referenced cluster is unknown or is `cluster`.
        """
        for name in self.referenced_clusters():
            if name not in known_clusters:
                raise ValueError(
                    f"unknown cluster '{name}' (known: {', '.join(known_clusters)})"
                )
            if name == cluster:
                raise ValueError(
                    f"cluster '{name}' is the cluster the resource is created in"
                )


class TestResource(BaseResource):
    """
    Resource created in a cluster for the duration of a test case.

    Subclasses set `Options` to the model of their `options`, and combine this
    class with the resource kind they create (e.g. a NetworkPolicyResource).

    Attributes:
        cluster (Cluster): The cluster the resource is created in.
        options (TestResourceOptions): The validated options of the resource.
    """

    Options: ClassVar[type[TestResourceOptions]] = TestResourceOptions

    cluster: Cluster
    options: TestResourceOptions

    def __init__(
        self,
        cluster: Cluster,
        name: str,
        namespace: str,
        options: TestResourceOptions | None = None,
    ):
        super().__init__(
            kubeconfig_path=cluster.kubeconfig_location,
            namespace=namespace,
            name=name,
            options=options if options is not None else self.Options(),
        )
        self.cluster = cluster
