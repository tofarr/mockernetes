"""A moto-like library for mocking Kubernetes API in Python tests."""

__version__ = "0.1.0"

from .mock import MockKubernetes, mock_kubernetes, patch_kubernetes
from .mock_apis import (
    MockAppsV1Api,
    MockCoreV1Api,
    MockCustomObjectsApi,
    MockNetworkingV1Api,
    MockPolicyV1Api,
)
from .mock_client import MockApiClient, MockKubernetesState

__all__ = [
    "MockKubernetes",
    "mock_kubernetes",
    "patch_kubernetes",
    "MockApiClient",
    "MockKubernetesState",
    "MockCoreV1Api",
    "MockAppsV1Api",
    "MockNetworkingV1Api",
    "MockPolicyV1Api",
    "MockCustomObjectsApi",
]


def main() -> None:
    """Entry point for the mockernetes CLI."""
    print("Hello from mockernetes!")
