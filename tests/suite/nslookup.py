from typing import Any
from kubernetes import client, config, stream


def test_nslookup(
    kubeconfig_location: str,
    namespace: str,
    pod: str,
    target_hostname: str,
    **_: Any,
) -> bool:
    """
    Tests DNS resolution from a source pod to a target hostname using nslookup.

    Executes an nslookup command in the source pod and checks if the exit code is 0,
    indicating successful DNS resolution.

    Args:
        kubeconfig_location (str): Path to the kubeconfig file.
        namespace (str): Namespace of the source pod.
        pod (str): Name of the source pod.
        target_hostname (str): Hostname to resolve.

    Returns:
        bool: True if the nslookup command exits with code 0, indicating successful resolution,
              False otherwise.
    """
    kube_client = client.CoreV1Api(
        api_client=config.new_client_from_config(kubeconfig_location)
    )

    exec_command = [
        "/bin/sh",
        "-c",
        f"nslookup {target_hostname}",
    ]

    resp = stream.stream(
        kube_client.connect_get_namespaced_pod_exec,
        pod,
        namespace,
        command=exec_command,
        stderr=True,
        stdin=False,
        stdout=True,
        tty=False,
    )

    exit_code = resp.returncode if hasattr(resp, "returncode") else 0

    return exit_code == 0
