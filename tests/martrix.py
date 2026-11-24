from clusters import Cluster
from input import TestConfig
from resources.test import TestResource
from .types import TestEntity


def generate_test_matrix(
    clusters: dict[str, Cluster],
) -> tuple[list[TestEntity], list[TestEntity]]:
    pods = [
        TestEntity(
            type="pod",
            test_suite=["ping", "curl"],
            name=p.name,
            namespace=p.namespace,
            cluster_name=c.name,
            ip=p.ip,
            hostname=p.name,
        )
        for c in clusters.values()
        for p in c.iter_pods()
    ]

    services = [
        TestEntity(
            type="service",
            test_suite=["curl"],
            name=s.name,
            namespace=s.namespace,
            cluster_name=c.name,
            ip=s.cluster_ip,
            hostname=s.name[1:],  # TODO: make generic
        )
        for c in clusters.values()
        for s in c.iter_services()
    ]

    internet = TestEntity(
        type="external",
        test_suite=["ping"],
        name="internet",
        namespace="",
        cluster_name="",
        ip="8.8.8.8",
        hostname=None,
    )

    nameserver = TestEntity(
        type="external",
        test_suite=["nslookup"],
        name="nameserver",
        namespace="",
        cluster_name="",
        ip=None,
        hostname="google.com",
    )

    sources = pods
    destinations = pods + services + [internet, nameserver]

    return sources, destinations


def generate_test_suite(
    tests: list[TestConfig], clusters: dict[str, Cluster]
) -> list[tuple[str, list[TestResource]]]:
    """Name and resources of each test case."""
    return [(test.name, test.build_resources(clusters)) for test in tests]
