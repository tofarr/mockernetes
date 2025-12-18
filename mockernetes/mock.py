"""
Main Mockernetes interface for easy integration with tests.

This module provides the primary interface for using Mockernetes as a drop-in
replacement for the Kubernetes client in tests.
"""

import inspect
from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional
from unittest.mock import patch

from kubernetes import client as k8s_client

from .mock_apis import (
    MockAppsV1Api,
    MockCoreV1Api,
    MockCustomObjectsApi,
    MockNetworkingV1Api,
    MockPolicyV1Api,
)
from .mock_client import MockApiClient, MockKubernetesState


class MockKubernetes:
    """
    Main Mockernetes class that provides a complete mock Kubernetes environment.

    This can be used as a context manager or with explicit start/stop methods.
    """

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        """
        Initialize MockKubernetes.

        Args:
            initial_state: Optional dictionary defining initial cluster state.
                          Format: {
                              'namespaces': ['default', 'kube-system'],
                              'pods': [pod_dict1, pod_dict2, ...],
                              'deployments': [deployment_dict1, ...],
                              # etc.
                          }
        """
        self.state = MockKubernetesState()
        self.mock_client = MockApiClient(self.state)
        self.patches = []
        self._is_active = False

        if initial_state:
            self._load_initial_state(initial_state)

    def start(self) -> None:
        """Start mocking Kubernetes APIs."""
        if self._is_active:
            return

        # Patch the main API client
        api_client_patch = patch(
            "kubernetes.client.ApiClient", return_value=self.mock_client
        )
        self.patches.append(api_client_patch)
        api_client_patch.start()

        # Patch the individual API classes to use our mock state
        core_v1_patch = patch(
            "kubernetes.client.CoreV1Api",
            lambda api_client=None: MockCoreV1Api(api_client, self.state),
        )
        self.patches.append(core_v1_patch)
        core_v1_patch.start()

        apps_v1_patch = patch(
            "kubernetes.client.AppsV1Api",
            lambda api_client=None: MockAppsV1Api(api_client, self.state),
        )
        self.patches.append(apps_v1_patch)
        apps_v1_patch.start()

        networking_v1_patch = patch(
            "kubernetes.client.NetworkingV1Api",
            lambda api_client=None: MockNetworkingV1Api(api_client, self.state),
        )
        self.patches.append(networking_v1_patch)
        networking_v1_patch.start()

        policy_v1_patch = patch(
            "kubernetes.client.PolicyV1Api",
            lambda api_client=None: MockPolicyV1Api(api_client, self.state),
        )
        self.patches.append(policy_v1_patch)
        policy_v1_patch.start()

        custom_objects_patch = patch(
            "kubernetes.client.CustomObjectsApi",
            lambda api_client=None: MockCustomObjectsApi(api_client, self.state),
        )
        self.patches.append(custom_objects_patch)
        custom_objects_patch.start()

        self._is_active = True

    def stop(self) -> None:
        """Stop mocking Kubernetes APIs."""
        if not self._is_active:
            return

        for patch_obj in self.patches:
            patch_obj.stop()
        self.patches.clear()
        self._is_active = False

    def reset(self) -> None:
        """Reset the mock state to empty."""
        self.state = MockKubernetesState()
        self.mock_client.state = self.state

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def _load_initial_state(self, initial_state: Dict[str, Any]) -> None:
        """Load initial state from configuration."""
        # Create namespaces first
        if "namespaces" in initial_state:
            for ns_name in initial_state["namespaces"]:
                if ns_name != "default":  # default already exists
                    ns = k8s_client.V1Namespace(
                        metadata=k8s_client.V1ObjectMeta(name=ns_name)
                    )
                    self.state.create_resource(None, "Namespace", ns)

        # Load other resources
        resource_loaders = {
            "pods": self._load_pods,
            "deployments": self._load_deployments,
            "services": self._load_services,
            "service_accounts": self._load_service_accounts,
            "pvcs": self._load_pvcs,
            "ingresses": self._load_ingresses,
        }

        for resource_type, loader in resource_loaders.items():
            if resource_type in initial_state:
                loader(initial_state[resource_type])

    def _load_pods(self, pods_data: list) -> None:
        """Load pods from configuration data."""
        for pod_data in pods_data:
            namespace = pod_data.get("metadata", {}).get("namespace", "default")
            # Create metadata object properly
            metadata_dict = pod_data.get("metadata", {})
            metadata = k8s_client.V1ObjectMeta(**metadata_dict)

            # Create spec object properly
            spec_dict = pod_data.get("spec", {})
            containers = []
            for container_data in spec_dict.get("containers", []):
                container = k8s_client.V1Container(**container_data)
                containers.append(container)
            spec = k8s_client.V1PodSpec(containers=containers)

            pod = k8s_client.V1Pod(metadata=metadata, spec=spec)
            self.state.create_resource(namespace, "Pod", pod)

    def _load_deployments(self, deployments_data: list) -> None:
        """Load deployments from configuration data."""
        for deployment_data in deployments_data:
            namespace = deployment_data.get("metadata", {}).get("namespace", "default")
            deployment = k8s_client.V1Deployment(**deployment_data)
            self.state.create_resource(namespace, "Deployment", deployment)

    def _load_services(self, services_data: list) -> None:
        """Load services from configuration data."""
        for service_data in services_data:
            namespace = service_data.get("metadata", {}).get("namespace", "default")
            service = k8s_client.V1Service(**service_data)
            self.state.create_resource(namespace, "Service", service)

    def _load_service_accounts(self, sa_data: list) -> None:
        """Load service accounts from configuration data."""
        for sa in sa_data:
            namespace = sa.get("metadata", {}).get("namespace", "default")
            service_account = k8s_client.V1ServiceAccount(**sa)
            self.state.create_resource(namespace, "ServiceAccount", service_account)

    def _load_pvcs(self, pvcs_data: list) -> None:
        """Load PVCs from configuration data."""
        for pvc_data in pvcs_data:
            namespace = pvc_data.get("metadata", {}).get("namespace", "default")
            pvc = k8s_client.V1PersistentVolumeClaim(**pvc_data)
            self.state.create_resource(namespace, "PersistentVolumeClaim", pvc)

    def _load_ingresses(self, ingresses_data: list) -> None:
        """Load ingresses from configuration data."""
        for ingress_data in ingresses_data:
            namespace = ingress_data.get("metadata", {}).get("namespace", "default")
            ingress = k8s_client.V1Ingress(**ingress_data)
            self.state.create_resource(namespace, "Ingress", ingress)

    # Convenience methods for accessing state
    def get_pods(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list:
        """Get pods from the mock state."""
        return self.state.list_resources(namespace, "Pod", label_selector)

    def get_deployments(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list:
        """Get deployments from the mock state."""
        return self.state.list_resources(namespace, "Deployment", label_selector)

    def get_services(
        self, namespace: str = "default", label_selector: Optional[str] = None
    ) -> list:
        """Get services from the mock state."""
        return self.state.list_resources(namespace, "Service", label_selector)

    def get_events(self) -> list:
        """Get all events from the mock state."""
        return self.state.events.copy()


# Convenience functions for common usage patterns
@contextmanager
def mock_kubernetes(
    initial_state: Optional[Dict[str, Any]] = None,
) -> Generator[MockKubernetes, None, None]:
    """
    Context manager for mocking Kubernetes APIs.

    Usage:
        with mock_kubernetes() as mock_k8s:
            # Your test code here
            pods = mock_k8s.get_pods()
    """
    mock_k8s = MockKubernetes(initial_state)
    with mock_k8s:
        yield mock_k8s


def patch_kubernetes(initial_state: Optional[Dict[str, Any]] = None):
    """
    Decorator for mocking Kubernetes APIs in test functions.

    Usage:
        @patch_kubernetes()
        def test_my_function():
            # Kubernetes APIs are now mocked
            pass
    """

    def decorator(func):
        def wrapper(*args, **kwargs):
            with mock_kubernetes(initial_state) as mock_k8s:
                # Add mock_k8s as first argument if function accepts it
                sig = inspect.signature(func)
                if len(sig.parameters) > len(args):
                    return func(mock_k8s, *args, **kwargs)
                return func(*args, **kwargs)

        return wrapper

    return decorator
