"""
Test basic Mockernetes functionality.

These tests verify that Mockernetes can successfully mock the Kubernetes API
and provide the expected behavior for basic operations.
"""

import pytest
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from mockernetes import MockKubernetes, mock_kubernetes


def test_import():
    """Test that mockernetes can be imported successfully."""
    import mockernetes

    assert mockernetes.__version__ == "0.1.0"


def test_context_manager():
    """Test using mockernetes as a context manager."""
    with mock_kubernetes() as mock_k8s:
        assert isinstance(mock_k8s, MockKubernetes)
        assert mock_k8s._is_active


def test_pod_creation_and_retrieval():
    """Test creating and retrieving pods."""
    with mock_kubernetes() as mock_k8s:
        # Create a pod using the mocked API
        core_api = k8s_client.CoreV1Api()

        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="test-pod"),
            spec=k8s_client.V1PodSpec(
                containers=[
                    k8s_client.V1Container(name="test-container", image="nginx:latest")
                ]
            ),
        )

        # Create the pod
        created_pod = core_api.create_namespaced_pod(namespace="default", body=pod)

        # Verify pod was created
        assert created_pod.metadata.name == "test-pod"
        assert created_pod.metadata.uid is not None
        assert created_pod.status.phase == "Running"  # Should be simulated as running

        # Retrieve the pod
        retrieved_pod = core_api.read_namespaced_pod(
            name="test-pod", namespace="default"
        )
        assert retrieved_pod.metadata.name == "test-pod"
        assert retrieved_pod.metadata.uid == created_pod.metadata.uid


def test_pod_listing_with_labels():
    """Test listing pods with label selectors."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        # Create pods with different labels
        pod1 = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(
                name="pod1", labels={"app": "web", "version": "v1"}
            ),
            spec=k8s_client.V1PodSpec(
                containers=[k8s_client.V1Container(name="web", image="nginx")]
            ),
        )

        pod2 = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(
                name="pod2", labels={"app": "api", "version": "v1"}
            ),
            spec=k8s_client.V1PodSpec(
                containers=[k8s_client.V1Container(name="api", image="python")]
            ),
        )

        core_api.create_namespaced_pod(namespace="default", body=pod1)
        core_api.create_namespaced_pod(namespace="default", body=pod2)

        # List all pods
        all_pods = core_api.list_namespaced_pod(namespace="default")
        assert len(all_pods.items) == 2

        # List pods with label selector
        web_pods = core_api.list_namespaced_pod(
            namespace="default", label_selector="app=web"
        )
        assert len(web_pods.items) == 1
        assert web_pods.items[0].metadata.name == "pod1"


def test_deployment_creation_and_pod_generation():
    """Test that deployments create pods automatically."""
    with mock_kubernetes() as mock_k8s:
        apps_api = k8s_client.AppsV1Api()
        core_api = k8s_client.CoreV1Api()

        # Create a deployment
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name="test-deployment", labels={"runtime_id": "test-runtime"}
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=2,
                selector=k8s_client.V1LabelSelector(match_labels={"app": "test"}),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels={"app": "test"}),
                    spec=k8s_client.V1PodSpec(
                        containers=[
                            k8s_client.V1Container(
                                name="test-container", image="nginx:latest"
                            )
                        ]
                    ),
                ),
            ),
        )

        # Create the deployment
        created_deployment = apps_api.create_namespaced_deployment(
            namespace="default", body=deployment
        )

        # Verify deployment was created
        assert created_deployment.metadata.name == "test-deployment"
        assert created_deployment.status.replicas == 2

        # Verify pods were created by the deployment controller simulation
        pods = core_api.list_namespaced_pod(
            namespace="default", label_selector="runtime_id=test-runtime"
        )
        assert len(pods.items) == 2

        # Verify pods have owner references
        for pod in pods.items:
            assert pod.metadata.owner_references is not None
            assert len(pod.metadata.owner_references) == 1
            owner_ref = pod.metadata.owner_references[0]
            assert owner_ref.kind == "Deployment"
            assert owner_ref.name == "test-deployment"


def test_service_creation():
    """Test creating services."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        service = k8s_client.V1Service(
            metadata=k8s_client.V1ObjectMeta(name="test-service"),
            spec=k8s_client.V1ServiceSpec(
                selector={"app": "test"},
                ports=[k8s_client.V1ServicePort(port=80, target_port=8080)],
            ),
        )

        created_service = core_api.create_namespaced_service(
            namespace="default", body=service
        )

        assert created_service.metadata.name == "test-service"
        assert created_service.spec.type == "ClusterIP"  # Default type
        assert created_service.spec.cluster_ip is not None  # Should be auto-generated


def test_owner_reference_cascading_deletion():
    """Test that deleting a deployment deletes its pods."""
    with mock_kubernetes() as mock_k8s:
        apps_api = k8s_client.AppsV1Api()
        core_api = k8s_client.CoreV1Api()

        # Create deployment (which creates pods)
        deployment = k8s_client.V1Deployment(
            metadata=k8s_client.V1ObjectMeta(
                name="test-deployment", labels={"runtime_id": "test-runtime"}
            ),
            spec=k8s_client.V1DeploymentSpec(
                replicas=1,
                selector=k8s_client.V1LabelSelector(match_labels={"app": "test"}),
                template=k8s_client.V1PodTemplateSpec(
                    metadata=k8s_client.V1ObjectMeta(labels={"app": "test"}),
                    spec=k8s_client.V1PodSpec(
                        containers=[k8s_client.V1Container(name="test", image="nginx")]
                    ),
                ),
            ),
        )

        apps_api.create_namespaced_deployment(namespace="default", body=deployment)

        # Verify pod exists
        pods_before = core_api.list_namespaced_pod(
            namespace="default", label_selector="runtime_id=test-runtime"
        )
        assert len(pods_before.items) == 1

        # Delete deployment
        apps_api.delete_namespaced_deployment(
            name="test-deployment", namespace="default"
        )

        # Verify pods are also deleted (cascading deletion)
        pods_after = core_api.list_namespaced_pod(
            namespace="default", label_selector="runtime_id=test-runtime"
        )
        assert len(pods_after.items) == 0


def test_pod_logs():
    """Test retrieving pod logs."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        # Create a pod
        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="test-pod"),
            spec=k8s_client.V1PodSpec(
                containers=[k8s_client.V1Container(name="test", image="nginx")]
            ),
        )

        core_api.create_namespaced_pod(namespace="default", body=pod)

        # Get logs
        logs = core_api.read_namespaced_pod_log(
            name="test-pod", namespace="default", container="test"
        )

        assert "Mock logs for pod test-pod in container test" in logs


def test_resource_not_found():
    """Test that accessing non-existent resources raises ApiException."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        with pytest.raises(ApiException) as exc_info:
            core_api.read_namespaced_pod(name="nonexistent", namespace="default")

        assert exc_info.value.status == 404
        assert exc_info.value.reason == "Not Found"


def test_resource_conflict():
    """Test that creating duplicate resources raises ApiException."""
    with mock_kubernetes() as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="test-pod"),
            spec=k8s_client.V1PodSpec(
                containers=[k8s_client.V1Container(name="test", image="nginx")]
            ),
        )

        # Create pod first time - should succeed
        core_api.create_namespaced_pod(namespace="default", body=pod)

        # Create same pod again - should fail
        with pytest.raises(ApiException) as exc_info:
            core_api.create_namespaced_pod(namespace="default", body=pod)

        assert exc_info.value.status == 409
        assert exc_info.value.reason == "Conflict"


def test_initial_state_loading():
    """Test loading initial state from configuration."""
    initial_state = {
        "namespaces": ["test-ns"],
        "pods": [
            {
                "metadata": {"name": "existing-pod", "namespace": "test-ns"},
                "spec": {"containers": [{"name": "test", "image": "nginx"}]},
            }
        ],
    }

    with mock_kubernetes(initial_state) as mock_k8s:
        core_api = k8s_client.CoreV1Api()

        # Verify namespace exists
        # Note: We don't have a direct namespace API in our mock yet,
        # but we can verify by creating a pod in it

        # Verify pod exists
        pod = core_api.read_namespaced_pod(name="existing-pod", namespace="test-ns")
        assert pod.metadata.name == "existing-pod"
        assert pod.metadata.namespace == "test-ns"


if __name__ == "__main__":
    pytest.main([__file__])
