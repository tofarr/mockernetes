#!/usr/bin/env python3
"""
Pytest integration examples for Mockernetes.

This file demonstrates different ways to integrate Mockernetes with pytest
for testing Kubernetes applications.
"""

import pytest
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from mockernetes import MockKubernetes, mock_kubernetes, patch_kubernetes


# Example 1: Using context manager directly in tests
def test_direct_context_manager():
    """Test using mock_kubernetes context manager directly."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        # Create a pod
        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="test-pod"),
            spec=k8s_client.V1PodSpec(
                containers=[k8s_client.V1Container(name="app", image="nginx")]
            ),
        )

        created_pod = core_api.create_namespaced_pod(namespace="default", body=pod)
        assert created_pod.metadata.name == "test-pod"
        assert created_pod.status.phase == "Running"


# Example 2: Using decorator
@patch_kubernetes()
def test_with_decorator():
    """Test using @patch_kubernetes decorator."""
    core_api = k8s_client.CoreV1Api()

    # Kubernetes APIs are automatically mocked
    pods = core_api.list_namespaced_pod(namespace="default")
    assert len(pods.items) == 0

    # Create a service
    service = k8s_client.V1Service(
        metadata=k8s_client.V1ObjectMeta(name="test-service"),
        spec=k8s_client.V1ServiceSpec(
            selector={"app": "test"}, ports=[k8s_client.V1ServicePort(port=80)]
        ),
    )

    created_service = core_api.create_namespaced_service(
        namespace="default", body=service
    )
    assert created_service.metadata.name == "test-service"
    assert created_service.spec.cluster_ip is not None


# Example 3: Using pytest fixtures
@pytest.fixture
def k8s_cluster():
    """Provide a clean Kubernetes cluster for each test."""
    with MockKubernetes() as mock_k8s:
        yield mock_k8s


@pytest.fixture
def k8s_cluster_with_data():
    """Provide a Kubernetes cluster with pre-loaded test data."""
    initial_state = {
        "namespaces": ["test-ns"],
        "pods": [
            {
                "metadata": {
                    "name": "existing-pod",
                    "namespace": "test-ns",
                    "labels": {"app": "existing"},
                },
                "spec": {"containers": [{"name": "app", "image": "nginx:1.20"}]},
            }
        ],
    }

    with MockKubernetes(initial_state) as mock_k8s:
        yield mock_k8s


def test_with_clean_fixture(k8s_cluster):
    """Test using a clean cluster fixture."""
    core_api = k8s_client.CoreV1Api()

    # Start with empty cluster
    pods = core_api.list_namespaced_pod(namespace="default")
    assert len(pods.items) == 0

    # Create a deployment
    apps_api = k8s_client.AppsV1Api()
    deployment = k8s_client.V1Deployment(
        metadata=k8s_client.V1ObjectMeta(name="test-deployment"),
        spec=k8s_client.V1DeploymentSpec(
            replicas=2,
            selector=k8s_client.V1LabelSelector(match_labels={"app": "test"}),
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(labels={"app": "test"}),
                spec=k8s_client.V1PodSpec(
                    containers=[k8s_client.V1Container(name="app", image="nginx")]
                ),
            ),
        ),
    )

    apps_api.create_namespaced_deployment(namespace="default", body=deployment)

    # Verify pods were created by controller
    pods = core_api.list_namespaced_pod(namespace="default", label_selector="app=test")
    assert len(pods.items) == 2


def test_with_preloaded_fixture(k8s_cluster_with_data):
    """Test using a cluster fixture with pre-loaded data."""
    core_api = k8s_client.CoreV1Api()

    # Verify existing pod is present
    pod = core_api.read_namespaced_pod(name="existing-pod", namespace="test-ns")
    assert pod.metadata.name == "existing-pod"
    assert pod.metadata.labels["app"] == "existing"

    # Create additional pod in same namespace
    new_pod = k8s_client.V1Pod(
        metadata=k8s_client.V1ObjectMeta(
            name="new-pod", namespace="test-ns", labels={"app": "new"}
        ),
        spec=k8s_client.V1PodSpec(
            containers=[k8s_client.V1Container(name="app", image="nginx:latest")]
        ),
    )

    core_api.create_namespaced_pod(namespace="test-ns", body=new_pod)

    # Verify both pods exist
    pods = core_api.list_namespaced_pod(namespace="test-ns")
    assert len(pods.items) == 2

    pod_names = [pod.metadata.name for pod in pods.items]
    assert "existing-pod" in pod_names
    assert "new-pod" in pod_names


# Example 4: Parameterized tests
@pytest.mark.parametrize("replica_count", [1, 3, 5])
def test_deployment_scaling(replica_count, k8s_cluster):
    """Test deployment scaling with different replica counts."""
    apps_api = k8s_client.AppsV1Api()
    core_api = k8s_client.CoreV1Api()

    deployment = k8s_client.V1Deployment(
        metadata=k8s_client.V1ObjectMeta(name="scalable-app"),
        spec=k8s_client.V1DeploymentSpec(
            replicas=replica_count,
            selector=k8s_client.V1LabelSelector(match_labels={"app": "scalable"}),
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(labels={"app": "scalable"}),
                spec=k8s_client.V1PodSpec(
                    containers=[k8s_client.V1Container(name="app", image="nginx")]
                ),
            ),
        ),
    )

    created_deployment = apps_api.create_namespaced_deployment(
        namespace="default", body=deployment
    )

    # Verify deployment has correct replica count
    assert created_deployment.spec.replicas == replica_count
    assert created_deployment.status.ready_replicas == replica_count

    # Verify correct number of pods were created
    pods = core_api.list_namespaced_pod(
        namespace="default", label_selector="app=scalable"
    )
    assert len(pods.items) == replica_count


# Example 5: Testing error conditions
def test_resource_not_found_error(k8s_cluster):
    """Test that proper errors are raised for non-existent resources."""
    core_api = k8s_client.CoreV1Api()

    with pytest.raises(ApiException) as exc_info:
        core_api.read_namespaced_pod(name="nonexistent", namespace="default")

    assert exc_info.value.status == 404
    assert exc_info.value.reason == "Not Found"


def test_resource_conflict_error(k8s_cluster):
    """Test that proper errors are raised for resource conflicts."""
    core_api = k8s_client.CoreV1Api()

    pod = k8s_client.V1Pod(
        metadata=k8s_client.V1ObjectMeta(name="duplicate-pod"),
        spec=k8s_client.V1PodSpec(
            containers=[k8s_client.V1Container(name="app", image="nginx")]
        ),
    )

    # Create pod first time - should succeed
    core_api.create_namespaced_pod(namespace="default", body=pod)

    # Try to create same pod again - should fail
    with pytest.raises(ApiException) as exc_info:
        core_api.create_namespaced_pod(namespace="default", body=pod)

    assert exc_info.value.status == 409
    assert exc_info.value.reason == "Conflict"


# Example 6: Testing complex scenarios
class TestRuntimeLifecycle:
    """Test class for complex runtime lifecycle scenarios."""

    @pytest.fixture(autouse=True)
    def setup_runtime(self, k8s_cluster):
        """Set up runtime test environment."""
        self.runtime_id = "test-runtime-456"
        self.namespace = "default"
        self.core_api = k8s_client.CoreV1Api()
        self.apps_api = k8s_client.AppsV1Api()
        self.policy_api = k8s_client.PolicyV1Api()

    def test_runtime_creation(self):
        """Test creating a complete runtime environment."""
        # Create ServiceAccount
        sa = k8s_client.V1ServiceAccount(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{self.runtime_id}",
                labels={"runtime_id": self.runtime_id},
            )
        )
        self.core_api.create_namespaced_service_account(
            namespace=self.namespace, body=sa
        )

        # Create Deployment
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{self.runtime_id}",
                labels={"runtime_id": self.runtime_id},
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": self.runtime_id}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(
                        labels={"runtime_id": self.runtime_id}
                    ),
                    spec=k8s_client.V1PodSpec(
                        service_account_name=f"runtime-{self.runtime_id}",
                        containers=[
                            k8s_client.V1Container(name="runtime", image="test-image")
                        ],
                    ),
                ),
            ),
        )

        created_deployment = self.apps_api.create_namespaced_deployment(
            namespace=self.namespace, body=deployment
        )

        # Verify deployment and pods
        assert created_deployment.metadata.name == f"runtime-{self.runtime_id}"

        pods = self.core_api.list_namespaced_pod(
            namespace=self.namespace, label_selector=f"runtime_id={self.runtime_id}"
        )
        assert len(pods.items) == 1
        assert pods.items[0].status.phase == "Running"

    def test_runtime_with_dependencies(self):
        """Test runtime with dependent resources."""
        # Create deployment first
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{self.runtime_id}",
                labels={"runtime_id": self.runtime_id},
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(
                    match_labels={"runtime_id": self.runtime_id}
                ),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(
                        labels={"runtime_id": self.runtime_id}
                    ),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(name="runtime", image="test")
                        ]
                    ),
                ),
            ),
        )

        created_deployment = self.apps_api.create_namespaced_deployment(
            namespace=self.namespace, body=deployment
        )

        # Create dependent resources with owner references
        owner_ref = k8s_client.V1OwnerReference(
            api_version="apps/v1",
            kind="Deployment",
            name=created_deployment.metadata.name,
            uid=created_deployment.metadata.uid,
        )

        # Service
        service = k8s_client.V1Service(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{self.runtime_id}", owner_references=[owner_ref]
            ),
            spec=k8s_client.V1ServiceSpec(
                selector={"runtime_id": self.runtime_id},
                ports=[k8s_client.V1ServicePort(port=80)],
            ),
        )
        self.core_api.create_namespaced_service(namespace=self.namespace, body=service)

        # PVC
        pvc = k8s_client.V1PersistentVolumeClaim(
            metadata=k8s_client.V1ObjectMeta(
                name=f"runtime-{self.runtime_id}", owner_references=[owner_ref]
            ),
            spec=k8s_client.V1PersistentVolumeClaimSpec(
                access_modes=["ReadWriteOnce"],
                resources=k8s_client.V1ResourceRequirements(
                    requests={"storage": "1Gi"}
                ),
            ),
        )
        self.core_api.create_namespaced_persistent_volume_claim(
            namespace=self.namespace, body=pvc
        )

        # Verify all resources exist
        assert self.core_api.read_namespaced_service(
            f"runtime-{self.runtime_id}", self.namespace
        )
        assert self.core_api.read_namespaced_persistent_volume_claim(
            f"runtime-{self.runtime_id}", self.namespace
        )

        # Test cascading deletion
        self.apps_api.delete_namespaced_deployment(
            name=f"runtime-{self.runtime_id}", namespace=self.namespace
        )

        # Verify dependent resources are deleted
        with pytest.raises(ApiException):
            self.core_api.read_namespaced_service(
                f"runtime-{self.runtime_id}", self.namespace
            )

        with pytest.raises(ApiException):
            self.core_api.read_namespaced_persistent_volume_claim(
                f"runtime-{self.runtime_id}", self.namespace
            )


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])
