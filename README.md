# Mockernetes

A moto-like library for mocking Kubernetes API in Python tests with stateful in-memory behavior.

## Features

- **Drop-in replacement** for `kubernetes.client.ApiClient` using patch requests
- **Stateful in-memory behavior** that simulates real Kubernetes cluster state
- **Shared fixtures** for test configurations and common scenarios
- **Resource lifecycle simulation** including pod phases, deployment controllers, etc.
- **Owner reference handling** with automatic cascading deletion
- **Label selector support** for realistic resource querying
- **Event generation** for monitoring and debugging test scenarios
- **Custom Resource support** for CRDs and Gateway API resources

## Installation

```bash
pip install mockernetes
```

## Quick Start

```python
from kubernetes import client as k8s_client
from mockernetes import mock_kubernetes

def test_my_kubernetes_code():
    with mock_kubernetes() as mock_k8s:
        # Your existing Kubernetes client code works unchanged
        core_api = k8s_client.CoreV1Api()
        
        # Create a pod
        pod = k8s_client.V1Pod(
            metadata=k8s_client.V1ObjectMeta(name="test-pod"),
            spec=k8s_client.V1PodSpec(
                containers=[
                    k8s_client.V1Container(name="app", image="nginx")
                ]
            )
        )
        created_pod = core_api.create_namespaced_pod(namespace="default", body=pod)
        
        # All operations are mocked but behave like real Kubernetes
        assert created_pod.status.phase == "Running"
        assert created_pod.metadata.uid is not None
```

## Advanced Usage

### Using as a Decorator

```python
from mockernetes import patch_kubernetes

@patch_kubernetes()
def test_with_decorator():
    core_api = k8s_client.CoreV1Api()
    # Kubernetes APIs are automatically mocked
    pods = core_api.list_namespaced_pod(namespace="default")
    assert len(pods.items) == 0
```

### Pre-configured Initial State

```python
initial_state = {
    'namespaces': ['production', 'staging'],
    'pods': [
        {
            'metadata': {
                'name': 'existing-pod',
                'namespace': 'production',
                'labels': {'app': 'web'}
            },
            'spec': {
                'containers': [{'name': 'web', 'image': 'nginx:1.20'}]
            }
        }
    ]
}

with mock_kubernetes(initial_state) as mock_k8s:
    core_api = k8s_client.CoreV1Api()
    pod = core_api.read_namespaced_pod(name="existing-pod", namespace="production")
    assert pod.metadata.labels['app'] == 'web'
```

### Deployment Controller Simulation

Mockernetes automatically simulates Kubernetes controllers:

```python
with mock_kubernetes() as mock_k8s:
    apps_api = k8s_client.AppsV1Api()
    core_api = k8s_client.CoreV1Api()
    
    # Create a deployment
    deployment = k8s_client.V1Deployment(
        metadata=k8s_client.V1ObjectMeta(name="web-app"),
        spec=k8s_client.V1DeploymentSpec(
            replicas=3,
            selector=k8s_client.V1LabelSelector(match_labels={"app": "web"}),
            template=k8s_client.V1PodTemplateSpec(
                metadata=k8s_client.V1ObjectMeta(labels={"app": "web"}),
                spec=k8s_client.V1PodSpec(
                    containers=[k8s_client.V1Container(name="web", image="nginx")]
                )
            )
        )
    )
    
    apps_api.create_namespaced_deployment(namespace="default", body=deployment)
    
    # Pods are automatically created by the simulated controller
    pods = core_api.list_namespaced_pod(namespace="default", label_selector="app=web")
    assert len(pods.items) == 3  # 3 replicas created automatically
    
    # Each pod has proper owner references
    for pod in pods.items:
        assert pod.metadata.owner_references[0].kind == "Deployment"
        assert pod.metadata.owner_references[0].name == "web-app"
```

### Cascading Deletion

Owner references are automatically handled:

```python
with mock_kubernetes() as mock_k8s:
    apps_api = k8s_client.AppsV1Api()
    core_api = k8s_client.CoreV1Api()
    
    # Create deployment (creates pods automatically)
    deployment = k8s_client.V1Deployment(...)
    created_deployment = apps_api.create_namespaced_deployment(namespace="default", body=deployment)
    
    # Create service with owner reference
    service = k8s_client.V1Service(
        metadata=k8s_client.V1ObjectMeta(
            name="web-service",
            owner_references=[k8s_client.V1OwnerReference(
                api_version='apps/v1',
                kind='Deployment',
                name=created_deployment.metadata.name,
                uid=created_deployment.metadata.uid,
            )]
        ),
        spec=k8s_client.V1ServiceSpec(
            selector={"app": "web"},
            ports=[k8s_client.V1ServicePort(port=80)]
        )
    )
    core_api.create_namespaced_service(namespace="default", body=service)
    
    # Delete deployment - service and pods are automatically deleted
    apps_api.delete_namespaced_deployment(name="web-app", namespace="default")
    
    # Verify cascading deletion
    pods = core_api.list_namespaced_pod(namespace="default", label_selector="app=web")
    assert len(pods.items) == 0  # Pods deleted
    
    with pytest.raises(ApiException):
        core_api.read_namespaced_service(name="web-service", namespace="default")  # Service deleted
```

### Custom Resources

Mockernetes supports custom resources through the CustomObjectsApi:

```python
with mock_kubernetes() as mock_k8s:
    custom_api = k8s_client.CustomObjectsApi()
    
    # Create HTTPRoute (Gateway API)
    httproute = {
        "apiVersion": "gateway.networking.k8s.io/v1",
        "kind": "HTTPRoute",
        "metadata": {"name": "my-route", "namespace": "default"},
        "spec": {
            "hostnames": ["example.com"],
            "rules": [{"backendRefs": [{"name": "my-service", "port": 80}]}]
        }
    }
    
    created_route = custom_api.create_namespaced_custom_object(
        group="gateway.networking.k8s.io",
        version="v1",
        namespace="default",
        plural="httproutes",
        body=httproute
    )
    
    assert created_route["metadata"]["name"] == "my-route"
```

## Supported APIs

Mockernetes currently supports:

- **CoreV1Api**: Pods, Services, ServiceAccounts, PersistentVolumeClaims, Namespaces
- **AppsV1Api**: Deployments, ReplicaSets, DaemonSets, StatefulSets
- **NetworkingV1Api**: Ingresses, NetworkPolicies
- **PolicyV1Api**: PodDisruptionBudgets
- **CustomObjectsApi**: Custom Resources (CRDs, Gateway API, etc.)

## Simulated Behaviors

### Pod Lifecycle
- Pods start in "Running" phase by default
- Container statuses are automatically populated
- Restart counts and ready states are simulated

### Deployment Controller
- Automatically creates pods based on replica count
- Sets up proper owner references
- Updates deployment status (ready replicas, etc.)

### Service Networking
- Automatically assigns ClusterIP addresses
- Validates port configurations
- Supports different service types

### Resource Management
- Generates unique UIDs for all resources
- Handles resource versions and timestamps
- Maintains proper metadata relationships

## Testing Patterns

### OpenHands Runtime API Pattern

Mockernetes was designed specifically to support the OpenHands runtime-api testing patterns:

```python
def test_runtime_lifecycle():
    with mock_kubernetes() as mock_k8s:
        runtime_id = "test-runtime-123"
        
        # Create all runtime resources
        create_runtime_resources(runtime_id)  # Your existing function
        
        # Verify resources exist
        pods = get_runtime_pods(runtime_id)  # Your existing function
        assert len(pods) == 1
        assert pods[0].status.phase == "Running"
        
        # Test cleanup
        delete_runtime(runtime_id)  # Your existing function
        
        # Verify cascading deletion
        pods_after = get_runtime_pods(runtime_id)
        assert len(pods_after) == 0
```

### Integration with Pytest

```python
import pytest
from mockernetes import MockKubernetes

@pytest.fixture
def k8s_cluster():
    """Provide a clean Kubernetes cluster for each test."""
    with MockKubernetes() as mock_k8s:
        yield mock_k8s

def test_with_fixture(k8s_cluster):
    core_api = k8s_client.CoreV1Api()
    # Test your code here
```

## Why Mockernetes?

Testing Kubernetes applications often requires complex setup or expensive cloud resources. Mockernetes provides a lightweight, fast alternative that:

- **Runs entirely in memory** - No external dependencies
- **Provides realistic behavior** - Simulates controllers, owner references, etc.
- **Supports complex scenarios** - Multi-resource interactions, cascading deletion
- **Integrates seamlessly** - Drop-in replacement for existing code
- **Eliminates infrastructure costs** - No need for real clusters in unit tests
- **Speeds up test execution** - In-memory operations are much faster

## Examples

See the `examples/` directory for comprehensive usage examples, including:

- Basic pod and service operations
- Deployment controller simulation
- OpenHands runtime-api patterns
- Custom resource handling
- Initial state configuration

## Contributing

Contributions are welcome! Please see our contributing guidelines for details.

## License

MIT License