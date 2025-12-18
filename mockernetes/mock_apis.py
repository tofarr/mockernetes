"""
Mock Kubernetes API classes - Drop-in replacements for kubernetes.client API classes

These classes provide the same interface as the real Kubernetes API classes
but operate on the mock state instead of a real cluster.
"""

from typing import Optional, List, Dict, Any
from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from .mock_client import MockKubernetesState


class MockCoreV1Api:
    """Mock implementation of kubernetes.client.CoreV1Api."""
    
    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (api_client.state if hasattr(api_client, 'state') else MockKubernetesState())
    
    # Namespace operations
    def create_namespace(self, body: k8s_client.V1Namespace, **kwargs) -> k8s_client.V1Namespace:
        """Create a namespace."""
        return self.state.create_resource(None, "Namespace", body)
    
    def delete_namespace(self, name: str, **kwargs) -> k8s_client.V1Status:
        """Delete a namespace."""
        self.state.delete_resource(None, "Namespace", name)
        return k8s_client.V1Status(status="Success")
    
    # Pod operations
    def create_namespaced_pod(self, namespace: str, body: k8s_client.V1Pod, **kwargs) -> k8s_client.V1Pod:
        """Create a pod in a namespace."""
        # Initialize pod status if not present
        if not body.status:
            body.status = k8s_client.V1PodStatus(
                phase="Pending",
                conditions=[],
                container_statuses=[]
            )
        
        pod = self.state.create_resource(namespace, "Pod", body)
        
        # Simulate pod lifecycle - move to Running after creation
        self._simulate_pod_startup(pod)
        
        return pod
    
    def read_namespaced_pod(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Pod:
        """Read a specific pod."""
        return self.state.get_resource(namespace, "Pod", name)
    
    def list_namespaced_pod(self, namespace: str, label_selector: Optional[str] = None, **kwargs) -> k8s_client.V1PodList:
        """List pods in a namespace."""
        pods = self.state.list_resources(namespace, "Pod", label_selector)
        return k8s_client.V1PodList(items=pods)
    
    def delete_namespaced_pod(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a pod."""
        self.state.delete_resource(namespace, "Pod", name)
        return k8s_client.V1Status(status="Success")
    
    def read_namespaced_pod_log(self, name: str, namespace: str, container: Optional[str] = None, 
                               previous: bool = False, **kwargs) -> str:
        """Read pod logs."""
        pod = self.state.get_resource(namespace, "Pod", name)
        
        # Simulate log content based on pod state
        if previous and pod.status.container_statuses:
            container_status = pod.status.container_statuses[0]
            if (container_status.last_state and 
                container_status.last_state.terminated and 
                container_status.last_state.terminated.message):
                return container_status.last_state.terminated.message
            return "Previous container logs"
        
        if pod.status.phase == "Running":
            return f"Mock logs for pod {name} in container {container or 'default'}"
        elif pod.status.phase == "Failed":
            return f"Error logs for failed pod {name}"
        else:
            return f"No logs available for pod {name} in phase {pod.status.phase}"
    
    # Service operations
    def create_namespaced_service(self, namespace: str, body: k8s_client.V1Service, **kwargs) -> k8s_client.V1Service:
        """Create a service."""
        # Set default service type if not specified
        if not body.spec.type:
            body.spec.type = "ClusterIP"
        
        # Generate cluster IP if not set
        if not body.spec.cluster_ip and body.spec.type == "ClusterIP":
            body.spec.cluster_ip = f"10.96.{len(self.state.get_resource_store(namespace, 'Service')) % 255}.{(len(self.state.get_resource_store(namespace, 'Service')) // 255) % 255}"
        
        return self.state.create_resource(namespace, "Service", body)
    
    def read_namespaced_service(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Service:
        """Read a specific service."""
        return self.state.get_resource(namespace, "Service", name)
    
    def list_namespaced_service(self, namespace: str, label_selector: Optional[str] = None, **kwargs) -> k8s_client.V1ServiceList:
        """List services in a namespace."""
        services = self.state.list_resources(namespace, "Service", label_selector)
        return k8s_client.V1ServiceList(items=services)
    
    def delete_namespaced_service(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a service."""
        self.state.delete_resource(namespace, "Service", name)
        return k8s_client.V1Status(status="Success")
    
    # ServiceAccount operations
    def create_namespaced_service_account(self, namespace: str, body: k8s_client.V1ServiceAccount, **kwargs) -> k8s_client.V1ServiceAccount:
        """Create a service account."""
        return self.state.create_resource(namespace, "ServiceAccount", body)
    
    def read_namespaced_service_account(self, name: str, namespace: str, **kwargs) -> k8s_client.V1ServiceAccount:
        """Read a specific service account."""
        return self.state.get_resource(namespace, "ServiceAccount", name)
    
    def delete_namespaced_service_account(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a service account."""
        self.state.delete_resource(namespace, "ServiceAccount", name)
        return k8s_client.V1Status(status="Success")
    
    # PersistentVolumeClaim operations
    def create_namespaced_persistent_volume_claim(self, namespace: str, body: k8s_client.V1PersistentVolumeClaim, **kwargs) -> k8s_client.V1PersistentVolumeClaim:
        """Create a PVC."""
        # Initialize status
        if not body.status:
            body.status = k8s_client.V1PersistentVolumeClaimStatus(phase="Pending")
        
        pvc = self.state.create_resource(namespace, "PersistentVolumeClaim", body)
        
        # Simulate PVC binding
        pvc.status.phase = "Bound"
        
        return pvc
    
    def read_namespaced_persistent_volume_claim(self, name: str, namespace: str, **kwargs) -> k8s_client.V1PersistentVolumeClaim:
        """Read a specific PVC."""
        return self.state.get_resource(namespace, "PersistentVolumeClaim", name)
    
    def delete_namespaced_persistent_volume_claim(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a PVC."""
        self.state.delete_resource(namespace, "PersistentVolumeClaim", name)
        return k8s_client.V1Status(status="Success")
    
    def _simulate_pod_startup(self, pod: k8s_client.V1Pod) -> None:
        """Simulate pod startup process."""
        # Create container statuses if not present
        if not pod.status.container_statuses and pod.spec.containers:
            pod.status.container_statuses = []
            for container in pod.spec.containers:
                container_status = k8s_client.V1ContainerStatus(
                    name=container.name,
                    ready=False,
                    restart_count=0,
                    image=container.image,
                    image_id=f"docker-pullable://{container.image}@sha256:mock",
                    state=k8s_client.V1ContainerState(
                        waiting=k8s_client.V1ContainerStateWaiting(reason="ContainerCreating")
                    )
                )
                pod.status.container_statuses.append(container_status)
        
        # Simulate transition to Running
        pod.status.phase = "Running"
        for container_status in pod.status.container_statuses or []:
            container_status.ready = True
            container_status.state = k8s_client.V1ContainerState(
                running=k8s_client.V1ContainerStateRunning()
            )


class MockAppsV1Api:
    """Mock implementation of kubernetes.client.AppsV1Api."""
    
    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (api_client.state if hasattr(api_client, 'state') else MockKubernetesState())
    
    def create_namespaced_deployment(self, namespace: str, body: k8s_client.V1Deployment, **kwargs) -> k8s_client.V1Deployment:
        """Create a deployment."""
        # Initialize status
        if not body.status:
            body.status = k8s_client.V1DeploymentStatus(
                replicas=0,
                ready_replicas=0,
                available_replicas=0,
                conditions=[]
            )
        
        deployment = self.state.create_resource(namespace, "Deployment", body)
        
        # Simulate deployment controller behavior
        self._simulate_deployment_controller(deployment, namespace)
        
        return deployment
    
    def read_namespaced_deployment(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Deployment:
        """Read a specific deployment."""
        return self.state.get_resource(namespace, "Deployment", name)
    
    def list_namespaced_deployment(self, namespace: str, label_selector: Optional[str] = None, **kwargs) -> k8s_client.V1DeploymentList:
        """List deployments in a namespace."""
        deployments = self.state.list_resources(namespace, "Deployment", label_selector)
        return k8s_client.V1DeploymentList(items=deployments)
    
    def delete_namespaced_deployment(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a deployment."""
        self.state.delete_resource(namespace, "Deployment", name)
        return k8s_client.V1Status(status="Success")
    
    def _simulate_deployment_controller(self, deployment: k8s_client.V1Deployment, namespace: str) -> None:
        """Simulate deployment controller creating pods."""
        replicas = deployment.spec.replicas or 1
        
        # Create pods for the deployment
        for i in range(replicas):
            pod_name = f"{deployment.metadata.name}-{deployment.metadata.uid[:8]}-{i}"
            
            # Create pod spec based on deployment template
            pod = k8s_client.V1Pod(
                metadata=k8s_client.V1ObjectMeta(
                    name=pod_name,
                    namespace=namespace,
                    labels=deployment.spec.template.metadata.labels.copy() if deployment.spec.template.metadata.labels else {},
                    owner_references=[
                        k8s_client.V1OwnerReference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=deployment.metadata.name,
                            uid=deployment.metadata.uid
                        )
                    ]
                ),
                spec=deployment.spec.template.spec,
                status=k8s_client.V1PodStatus(phase="Pending")
            )
            
            # Add runtime_id label if present in deployment
            if deployment.metadata.labels and 'runtime_id' in deployment.metadata.labels:
                if not pod.metadata.labels:
                    pod.metadata.labels = {}
                pod.metadata.labels['runtime_id'] = deployment.metadata.labels['runtime_id']
            
            # Store the pod
            try:
                core_api = MockCoreV1Api(state=self.state)
                core_api.create_namespaced_pod(namespace, pod)
            except ApiException:
                pass  # Pod might already exist
        
        # Update deployment status
        deployment.status.replicas = replicas
        deployment.status.ready_replicas = replicas
        deployment.status.available_replicas = replicas


class MockNetworkingV1Api:
    """Mock implementation of kubernetes.client.NetworkingV1Api."""
    
    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (api_client.state if hasattr(api_client, 'state') else MockKubernetesState())
    
    def create_namespaced_ingress(self, namespace: str, body: k8s_client.V1Ingress, **kwargs) -> k8s_client.V1Ingress:
        """Create an ingress."""
        return self.state.create_resource(namespace, "Ingress", body)
    
    def read_namespaced_ingress(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Ingress:
        """Read a specific ingress."""
        return self.state.get_resource(namespace, "Ingress", name)
    
    def delete_namespaced_ingress(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete an ingress."""
        self.state.delete_resource(namespace, "Ingress", name)
        return k8s_client.V1Status(status="Success")


class MockPolicyV1Api:
    """Mock implementation of kubernetes.client.PolicyV1Api."""
    
    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (api_client.state if hasattr(api_client, 'state') else MockKubernetesState())
    
    def create_namespaced_pod_disruption_budget(self, namespace: str, body: k8s_client.V1PodDisruptionBudget, **kwargs) -> k8s_client.V1PodDisruptionBudget:
        """Create a PodDisruptionBudget."""
        return self.state.create_resource(namespace, "PodDisruptionBudget", body)
    
    def read_namespaced_pod_disruption_budget(self, name: str, namespace: str, **kwargs) -> k8s_client.V1PodDisruptionBudget:
        """Read a specific PodDisruptionBudget."""
        return self.state.get_resource(namespace, "PodDisruptionBudget", name)
    
    def delete_namespaced_pod_disruption_budget(self, name: str, namespace: str, **kwargs) -> k8s_client.V1Status:
        """Delete a PodDisruptionBudget."""
        self.state.delete_resource(namespace, "PodDisruptionBudget", name)
        return k8s_client.V1Status(status="Success")


class MockCustomObjectsApi:
    """Mock implementation of kubernetes.client.CustomObjectsApi."""
    
    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (api_client.state if hasattr(api_client, 'state') else MockKubernetesState())
    
    def create_namespaced_custom_object(self, group: str, version: str, namespace: str, 
                                      plural: str, body: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Create a custom resource."""
        kind = plural.capitalize().rstrip('s')  # Simple pluralization reversal
        
        # Convert dict to a simple object for storage
        class CustomResource:
            def __init__(self, data):
                self.__dict__.update(data)
                if 'metadata' in data:
                    self.metadata = k8s_client.V1ObjectMeta(**data['metadata'])
        
        resource = CustomResource(body)
        created = self.state.create_resource(namespace, f"{group}/{version}/{kind}", resource)
        
        # Return as dict
        return body
    
    def get_namespaced_custom_object(self, group: str, version: str, namespace: str, 
                                   plural: str, name: str, **kwargs) -> Dict[str, Any]:
        """Get a custom resource."""
        kind = plural.capitalize().rstrip('s')
        resource = self.state.get_resource(namespace, f"{group}/{version}/{kind}", name)
        
        # Convert back to dict format
        result = resource.__dict__.copy()
        
        # Convert metadata back to dict if it's a V1ObjectMeta
        if hasattr(resource, 'metadata') and hasattr(resource.metadata, 'name'):
            result['metadata'] = {
                'name': resource.metadata.name,
                'namespace': resource.metadata.namespace,
                'uid': resource.metadata.uid,
                'labels': resource.metadata.labels or {},
                'annotations': resource.metadata.annotations or {}
            }
        
        return result
    
    def delete_namespaced_custom_object(self, group: str, version: str, namespace: str, 
                                      plural: str, name: str, **kwargs) -> Dict[str, Any]:
        """Delete a custom resource."""
        kind = plural.capitalize().rstrip('s')
        self.state.delete_resource(namespace, f"{group}/{version}/{kind}", name)
        return {"status": "Success"}