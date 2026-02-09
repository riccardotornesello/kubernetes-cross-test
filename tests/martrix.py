from clusters import Cluster
from .execution import TestEntity
from resources.test import test_resources


def generate_test_matrix(
    clusters: dict[str, Cluster],
) -> tuple[list[TestEntity], list[TestEntity]]:
    pods = [
        TestEntity(
            type="pod",
            test_suite=["ping", "curl"],
            ip=p.ip,
            name=p.name,
            namespace=ns,
            cluster_name=c.name,
        )
        for c in clusters.values()
        for ns in c.namespaces
        for p in c.pods[ns]
    ]

    services = [
        TestEntity(
            type="service",
            test_suite=["curl"],
            name=s.name,
            namespace=ns,
            cluster_name=c.name,
            ip=s.cluster_ip,
        )
        for c in clusters.values()
        for ns in c.namespaces
        for s in c.services[ns]
    ]

    internet = TestEntity(
        type="external",
        test_suite=["ping"],
        name="internet",
        namespace="",
        ip="8.8.8.8",
        cluster_name=None,
    )

    sources = pods
    destinations = pods + services + [internet]

    return sources, destinations


def generate_test_suite(
    test_cases: list[dict], clusters: dict[str, Cluster]
) -> list[tuple[str, list[TestEntity]]]:
    test_suites = []
    kubeconfigs = {c.name: c.kubeconfig_location for c in clusters.values()}

    for test_case in test_cases:
        test_name = test_case.get("name", "Unnamed Test Suite")
        resources = test_case.get("resources", [])
        test_entities = []

        for resource in resources:
            resource_type = resource.get("type")
            resource_class = test_resources.get(resource_type)

            if not resource_class:
                raise ValueError(f"Unknown resource type: {resource_type}")

            test_entity = resource_class(
                kubeconfig_path=kubeconfigs[resource["cluster"]],
                namespace=resource["namespace"],
                name=resource["name"],
                options={
                    **resource.get("options", {}),
                    "clusters": clusters,
                    "cluster": resource["cluster"],
                },
            )
            test_entities.append(test_entity)

        test_suites.append((test_name, test_entities))

    return test_suites
