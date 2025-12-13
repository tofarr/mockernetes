"""A moto-like library for mocking Kubernetes API in Python tests."""

__version__ = "0.1.0"

from .mock import MockKubernetes, mock_kubernetes, patch_kubernetes
from .mock_client import MockApiClient, MockKubernetesState
from .mock_apis import (
    MockCoreV1Api,
    MockAppsV1Api,
    MockNetworkingV1Api,
    MockPolicyV1Api,
    MockCustomObjectsApi
)

__all__ = [
    'MockKubernetes',
    'mock_kubernetes', 
    'patch_kubernetes',
    'MockApiClient',
    'MockKubernetesState',
    'MockCoreV1Api',
    'MockAppsV1Api',
    'MockNetworkingV1Api',
    'MockPolicyV1Api',
    'MockCustomObjectsApi',
]

def main() -> None:
    print("Hello from mockernetes!")
