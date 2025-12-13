# OpenHands Runtime-API Kubernetes Usage Analysis

## Overview

After analyzing the OpenHands runtime-api project, I've identified the key Kubernetes API usage patterns that Mockernetes should support. This analysis will guide our implementation priorities.

## Key Kubernetes Resources Used

### Core Resources
1. **Deployments** (`apps/v1`) - Primary workload resource
2. **Pods** (`v1`) - Individual container instances
3. **Services** (`v1`) - Network access to pods
4. **ServiceAccounts** (`v1`) - Pod identity and permissions
5. **PersistentVolumeClaims** (`v1`) - Storage requests
6. **PodDisruptionBudgets** (`policy/v1`) - Availability guarantees

### Networking Resources
7. **Ingress** (`networking.k8s.io/v1`) - HTTP routing (traditional mode)
8. **HTTPRoute** (`gateway.networking.k8s.io/v1`) - HTTP routing (Gateway API mode)

## API Operations Patterns

### Resource Creation Flow
The runtime-api follows this pattern when creating a runtime:

```python
# 1. Create ServiceAccount
k8s_api.create_namespaced_service_account(namespace=K8S_NAMESPACE, body=sa_manifest)

# 2. Create Deployment
deployment = apps_v1_api.create_namespaced_deployment(namespace=K8S_NAMESPACE, body=deployment_manifest)

# 3. Set up owner references for cleanup
owner_reference = k8s_client.V1OwnerReference(
    api_version='apps/v1',
    kind='Deployment', 
    name=deployment.metadata.name,
    uid=deployment.metadata.uid,
)

# 4. Create dependent resources with owner references
service_manifest.metadata.owner_references = [owner_reference]
pvc_manifest.metadata.owner_references = [owner_reference]
pdb_manifest.metadata.owner_references = [owner_reference]

# 5. Create remaining resources
policy_v1_api.create_namespaced_pod_disruption_budget(namespace=K8S_NAMESPACE, body=pdb_manifest)
k8s_api.create_namespaced_service(namespace=K8S_NAMESPACE, body=service_manifest)
k8s_api.create_namespaced_persistent_volume_claim(namespace=K8S_NAMESPACE, body=pvc_manifest)
```

### Resource Querying Patterns
```python
# Get pods for a runtime
pods = core_v1_api.list_namespaced_pod(
    namespace=K8S_NAMESPACE,
    label_selector=f'runtime_id={runtime_id}'
)

# Get pod logs
pod_logs = api.read_namespaced_pod_log(
    name=pod.metadata.name,
    namespace=pod.metadata.namespace,
    container='runtime',
    previous=True  # For crashed containers
)

# Check deployment status
deployment = apps_v1_api.read_namespaced_deployment(
    name=deployment_name,
    namespace=K8S_NAMESPACE
)
```

### Resource Deletion Patterns
```python
# Delete deployment (owner references handle cascading deletion)
apps_v1_api.delete_namespaced_deployment(
    name=deployment_name,
    namespace=K8S_NAMESPACE
)

# Manual cleanup of specific resources
k8s_api.delete_namespaced_service_account(name=sa_name, namespace=K8S_NAMESPACE)
k8s_api.delete_namespaced_service(name=service_name, namespace=K8S_NAMESPACE)
k8s_api.delete_namespaced_persistent_volume_claim(name=pvc_name, namespace=K8S_NAMESPACE)
```

## Testing Patterns Observed

### Mock Usage in Tests
The runtime-api uses standard Python mocking for unit tests:

```python
from unittest.mock import Mock, patch
from kubernetes.client import ApiException as K8sApiException

# Mock pod objects
def mock_running_pod():
    pod = Mock()
    pod.status.phase = 'Running'
    container_status = Mock()
    container_status.ready = True
    container_status.state.running = True
    container_status.restart_count = 0
    pod.status.container_statuses = [container_status]
    return pod

# Mock API calls
with patch('kubernetes.client.CoreV1Api') as mock_api:
    mock_api.return_value.read_namespaced_pod_log.return_value = 'Previous container logs'
    result = get_pods_summary(pods, '..runtime_url..')
```

### Integration Testing
- Uses KIND (Kubernetes in Docker) for integration tests
- Shell scripts test full lifecycle operations
- Tests real Kubernetes behavior end-to-end

## Key Requirements for Mockernetes

### 1. Resource State Management
- **In-memory storage** of all Kubernetes resources
- **Namespace isolation** - resources scoped to namespaces
- **Label and field selectors** for filtering
- **Owner reference handling** for cascading deletion

### 2. Controller Simulation
- **Deployment → ReplicaSet → Pod** relationship simulation
- **Pod lifecycle management** (Pending → Running → Succeeded/Failed)
- **Container status simulation** (waiting, running, terminated)
- **Restart count tracking**

### 3. API Compatibility
- **Standard Kubernetes API endpoints** (`/api/v1`, `/apis/apps/v1`, etc.)
- **HTTP status codes** (200, 201, 404, 409, etc.)
- **Error responses** matching Kubernetes API format
- **Resource versioning** and optimistic concurrency

### 4. Advanced Features
- **Owner references** and garbage collection
- **Resource quotas** and limits
- **Events generation** for resource changes
- **Custom Resource Definitions** (CRDs) support

## Implementation Priority

### Phase 1: Core Resources (MVP)
1. **Namespaces** - Basic scoping
2. **Pods** - Core workload unit
3. **Services** - Basic networking
4. **ConfigMaps/Secrets** - Configuration data

### Phase 2: Workload Controllers
1. **Deployments** - Declarative pod management
2. **ReplicaSets** - Pod replication
3. **Controller simulation** - Deployment → ReplicaSet → Pod

### Phase 3: Advanced Features
1. **PersistentVolumeClaims** - Storage
2. **ServiceAccounts** - Identity
3. **Ingress/HTTPRoute** - Advanced networking
4. **PodDisruptionBudgets** - Availability

### Phase 4: Testing Integration
1. **Pytest plugin** - Easy test integration
2. **Decorator support** - `@mock_kubernetes`
3. **Context manager** - `with mock_kubernetes():`
4. **Configuration options** - Custom behaviors

## Architecture Recommendations

### 1. HTTP Server Approach
```python
# Use Flask/FastAPI to implement Kubernetes API endpoints
@app.post("/api/v1/namespaces/{namespace}/pods")
def create_pod(namespace: str, pod: V1Pod):
    # Validate and store pod
    # Simulate controller behavior
    # Return created pod with status
```

### 2. State Management
```python
class KubernetesState:
    def __init__(self):
        self.namespaces = {}  # namespace -> resources
        self.events = []      # event log
        self.controllers = [] # active controllers
    
    def create_resource(self, namespace, kind, resource):
        # Store resource
        # Trigger controllers
        # Generate events
```

### 3. Controller Simulation
```python
class DeploymentController:
    def reconcile(self, deployment):
        # Create/update ReplicaSet
        # Scale pods to match replicas
        # Update deployment status
```

This analysis provides a solid foundation for implementing Mockernetes with the features most needed by real-world Kubernetes applications like OpenHands runtime-api.