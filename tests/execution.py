import concurrent.futures
import dataclasses

from tqdm import tqdm

from utils.network import remap_ip
from clusters import Cluster
from tests.types import Test, TestEntity


def run_tests(
    sources: list[TestEntity],
    destinations: list[TestEntity],
    clusters: dict[str, Cluster],
    max_workers: int = 10,
) -> list[Test]:
    """
    Runs network connectivity tests between all source and destination entities.

    Creates and executes test cases for all valid source-destination pairs,
    running tests in parallel using a thread pool. Tests include:
    - curl tests for both pods and services
    - ping tests for pods only (services don't support ping)

    Steps:
    1. Generate test cases for all valid source-destination pairs
    2. Skip self-to-self tests
    3. Skip cross-cluster service tests (services are cluster-local)
    4. Remap IPs for cross-cluster pod tests
    5. Execute tests in parallel using ThreadPoolExecutor
    6. Display progress with a progress bar

    Args:
        sources (list[TestEntity]): List of source entities to test from.
        destinations (list[TestEntity]): List of destination entities to test to.
        clusters (dict[str, Cluster]): List of clusters for IP remapping.
        max_workers (int, optional): Maximum number of concurrent test threads. Defaults to 5.

    Returns:
        list[Test]: List of Test objects with results populated.
    """
    tests: list[Test] = []

    remapped_cidrs = {c.name: c.remapped_cidrs for c in clusters.values()}
    kubeconfigs = {c.name: c.kubeconfig_location for c in clusters.values()}

    for source in sources:
        for destination in destinations:
            # Skip testing to self
            if is_same_peer(source, destination):
                continue

            # Skip testing service from pod in different cluster
            if (
                destination.type == "service"
                and source.cluster_name != destination.cluster_name
            ):
                continue

            # Remap IP if necessary
            target_ip = destination.ip
            if (
                destination.cluster_name
                and source.cluster_name != destination.cluster_name
            ):
                # Skip if the destination is in a cluster that cannot be reached from the source cluster
                if destination.cluster_name not in remapped_cidrs[source.cluster_name]:
                    continue

                target_ip = remap_ip(
                    target_ip,
                    remapped_cidrs[source.cluster_name][destination.cluster_name],
                )

            # Create the test list
            for test_type in destination.test_suite:
                tests.append(
                    Test(
                        test_type=test_type,
                        src=source,
                        dst=dataclasses.replace(destination, ip=target_ip),
                        kubeconfig_location=kubeconfigs[source.cluster_name],
                    )
                )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(test.run) for test in tests]

        for future in tqdm(
            concurrent.futures.as_completed(futures),
            total=len(futures),
            desc="Running tests",
        ):
            try:
                future.result()
            except Exception as exc:
                print(f"Generated an exception: {exc}")

    return tests


def is_same_peer(src: TestEntity, dst: TestEntity) -> bool:
    """
    Determines if the source and destination entities are the same peer.

    Compares the name, namespace, and cluster name of the source and destination
    entities to determine if they refer to the same peer.

    Args:
        src (TestEntity): The source entity.
        dst (TestEntity): The destination entity.

    Returns:
        bool: True if src and dst refer to the same peer, False otherwise.
    """
    return (
        src.name == dst.name
        and src.namespace == dst.namespace
        and src.cluster_name == dst.cluster_name
    )
