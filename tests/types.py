from dataclasses import dataclass
from typing import Literal
from .suite import test_suite


TestType = Literal["ping", "curl"]


@dataclass
class TestEntity:
    type: Literal["pod", "service", "external"]
    test_suite: list[TestType]
    ip: str
    name: str
    namespace: str
    cluster_name: str | None


@dataclass
class Test:
    test_type: TestType
    src: TestEntity
    dst: TestEntity
    kubeconfig_location: str
    result: bool | None = None

    def run(self) -> None:
        """
        Executes the test and stores the result.

        Runs the appropriate test function (ping or curl) based on test_type
        and updates the result attribute with the outcome.

        Raises:
            ValueError: If test_type is not "ping" or "curl".
        """
        # TODO: make dynamic
        target_hostname = self.dst.name
        if target_hostname[0] == "s":
            target_hostname = "p" + target_hostname[1:]

        test_params = {
            "kubeconfig_location": self.kubeconfig_location,
            "namespace": self.src.namespace,
            "pod": self.src.name,
            "target_ip": self.dst.ip,
            "target_hostname": target_hostname,
        }

        test_function = test_suite.get(self.test_type)
        if test_function is None:
            raise ValueError(f"Unknown test type: {self.test_type}")

        self.result = test_function(**test_params)
