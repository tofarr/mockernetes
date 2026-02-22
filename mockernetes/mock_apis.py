"""
Mock Kubernetes API classes - Drop-in replacements for kubernetes.client API classes

These classes provide the same interface as the real Kubernetes API classes
but operate on the mock state instead of a real cluster.
"""

from typing import Any, Dict, Optional

from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException

from .mock_client import MockKubernetesState


class MockCoreV1Api:
    """Mock implementation of kubernetes.client.CoreV1Api."""

    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (
            api_client.state if hasattr(api_client, "state") else MockKubernetesState()
        )

    # Namespace operations
    def create_namespace(
        self, body: k8s_client.V1Namespace, **_kwargs
    ) -> k8s_client.V1Namespace:
        """Create a namespace."""
        return self.state.create_resource(None, "Namespace", body)

    def delete_namespace(self, name: str, **_kwargs) -> k8s_client.V1Status:
        """Delete a namespace."""
        self.state.delete_resource(None, "Namespace", name)
        return k8s_client.V1Status(status="Success")

    # Pod operations
    def create_namespaced_pod(
        self, namespace: str, body: k8s_client.V1Pod, **_kwargs
    ) -> k8s_client.V1Pod:
        """Create a pod in a namespace."""
        # Initialize pod status if not present
        if not body.status:
            body.status = k8s_client.V1PodStatus(
                phase="Pending", conditions=[], container_statuses=[]
            )

        pod = self.state.create_resource(namespace, "Pod", body)

        # Simulate pod lifecycle - move to Running after creation
        self._simulate_pod_startup(pod)

        return pod

    def read_namespaced_pod(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Pod:
        """Read a specific pod."""
        return self.state.get_resource(namespace, "Pod", name)

    def list_namespaced_pod(
        self, namespace: str, label_selector: Optional[str] = None, **_kwargs
    ) -> k8s_client.V1PodList:
        """List pods in a namespace."""
        pods = self.state.list_resources(namespace, "Pod", label_selector)
        return k8s_client.V1PodList(items=pods)

    def delete_namespaced_pod(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
        """Delete a pod."""
        self.state.delete_resource(namespace, "Pod", name)
        return k8s_client.V1Status(status="Success")

    def read_namespaced_pod_log(
        self,
        name: str,
        namespace: str,
        container: Optional[str] = None,
        previous: bool = False,
        **_kwargs,
    ) -> str:
        """Read pod logs."""
        pod = self.state.get_resource(namespace, "Pod", name)

        # Simulate log content based on pod state
        if previous and pod.status.container_statuses:
            container_status = pod.status.container_statuses[0]
            if (
                container_status.last_state
                and container_status.last_state.terminated
                and container_status.last_state.terminated.message
            ):
                return container_status.last_state.terminated.message
            return "Previous container logs"

        if pod.status.phase == "Running":
            return f"Mock logs for pod {name} in container {container or 'default'}"
        if pod.status.phase == "Failed":
            return f"Error logs for failed pod {name}"
        return f"No logs available for pod {name} in phase {pod.status.phase}"

    # Service operations
    def create_namespaced_service(
        self, namespace: str, body: k8s_client.V1Service, **_kwargs
    ) -> k8s_client.V1Service:
        """Create a service."""
        # Set default service type if not specified
        if not body.spec.type:
            body.spec.type = "ClusterIP"

        # Generate cluster IP if not set
        if not body.spec.cluster_ip and body.spec.type == "ClusterIP":
            service_count = len(self.state.get_resource_store(namespace, "Service"))
            body.spec.cluster_ip = (
                f"10.96.{service_count % 255}.{(service_count // 255) % 255}"
            )

        return self.state.create_resource(namespace, "Service", body)

    def read_namespaced_service(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Service:
        """Read a specific service."""
        return self.state.get_resource(namespace, "Service", name)

    def list_namespaced_service(
        self, namespace: str, label_selector: Optional[str] = None, **_kwargs
    ) -> k8s_client.V1ServiceList:
        """List services in a namespace."""
        services = self.state.list_resources(namespace, "Service", label_selector)
        return k8s_client.V1ServiceList(items=services)

    def delete_namespaced_service(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
        """Delete a service."""
        self.state.delete_resource(namespace, "Service", name)
        return k8s_client.V1Status(status="Success")

    # ServiceAccount operations
    def create_namespaced_service_account(
        self, namespace: str, body: k8s_client.V1ServiceAccount, **_kwargs
    ) -> k8s_client.V1ServiceAccount:
        """Create a service account."""
        return self.state.create_resource(namespace, "ServiceAccount", body)

    def read_namespaced_service_account(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1ServiceAccount:
        """Read a specific service account."""
        return self.state.get_resource(namespace, "ServiceAccount", name)

    def delete_namespaced_service_account(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
        """Delete a service account."""
        self.state.delete_resource(namespace, "ServiceAccount", name)
        return k8s_client.V1Status(status="Success")

    # PersistentVolumeClaim operations
    def create_namespaced_persistent_volume_claim(
        self, namespace: str, body: k8s_client.V1PersistentVolumeClaim, **_kwargs
    ) -> k8s_client.V1PersistentVolumeClaim:
        """Create a PVC."""
        # Initialize status
        if not body.status:
            body.status = k8s_client.V1PersistentVolumeClaimStatus(phase="Pending")

        pvc = self.state.create_resource(namespace, "PersistentVolumeClaim", body)

        # Simulate PVC binding
        pvc.status.phase = "Bound"

        return pvc

    def read_namespaced_persistent_volume_claim(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1PersistentVolumeClaim:
        """Read a specific PVC."""
        return self.state.get_resource(namespace, "PersistentVolumeClaim", name)

    def delete_namespaced_persistent_volume_claim(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
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
                        waiting=k8s_client.V1ContainerStateWaiting(
                            reason="ContainerCreating"
                        )
                    ),
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
        self.state = state or (
            api_client.state if hasattr(api_client, "state") else MockKubernetesState()
        )

    def create_namespaced_deployment(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        namespace: str,
        body: k8s_client.V1Deployment,
        pretty: Optional[str] = None,  # pylint: disable=unused-argument
        dry_run: Optional[str] = None,  # pylint: disable=unused-argument
        field_manager: Optional[str] = None,  # pylint: disable=unused-argument
        field_validation: Optional[str] = None,  # pylint: disable=unused-argument
        **_kwargs,
    ) -> k8s_client.V1Deployment:
        """Create a deployment."""
        # Initialize status
        if not body.status:
            body.status = k8s_client.V1DeploymentStatus(
                replicas=0, ready_replicas=0, available_replicas=0, conditions=[]
            )

        deployment = self.state.create_resource(namespace, "Deployment", body)

        # Simulate deployment controller behavior
        self._simulate_deployment_controller(deployment, namespace)

        return deployment

    def read_namespaced_deployment(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        name: str,
        namespace: str,
        pretty: Optional[str] = None,  # pylint: disable=unused-argument
        exact: Optional[bool] = None,  # pylint: disable=unused-argument
        export: Optional[bool] = None,  # pylint: disable=unused-argument
        **_kwargs,
    ) -> k8s_client.V1Deployment:
        """Read a specific deployment."""
        return self.state.get_resource(namespace, "Deployment", name)

    def list_namespaced_deployment(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        namespace: str,
        pretty: Optional[str] = None,  # pylint: disable=unused-argument
        label_selector: Optional[str] = None,
        field_selector: Optional[str] = None,  # pylint: disable=unused-argument
        include_uninitialized: Optional[bool] = None,  # pylint: disable=unused-argument
        limit: Optional[int] = None,  # pylint: disable=unused-argument
        continue_token: Optional[str] = None,  # pylint: disable=unused-argument
        **_kwargs,
    ) -> k8s_client.V1DeploymentList:
        """List deployments in a namespace."""
        deployments = self.state.list_resources(namespace, "Deployment", label_selector)
        return k8s_client.V1DeploymentList(items=deployments)

    def delete_namespaced_deployment(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        name: str,
        namespace: str,
        pretty: Optional[str] = None,  # pylint: disable=unused-argument
        dry_run: Optional[str] = None,  # pylint: disable=unused-argument
        grace_period_seconds: Optional[int] = None,  # pylint: disable=unused-argument
        orphan_dependents: Optional[bool] = None,  # pylint: disable=unused-argument
        propagation_policy: Optional[str] = None,  # pylint: disable=unused-argument
        # pylint: disable=unused-argument
        body: Optional[k8s_client.V1DeleteOptions] = None,
        **_kwargs,
    ) -> k8s_client.V1Status:
        """Delete a deployment."""
        self.state.delete_resource(namespace, "Deployment", name)
        return k8s_client.V1Status(status="Success")

    def patch_namespaced_deployment(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        name: str,
        namespace: str,
        body: Any,
        pretty: Optional[str] = None,  # pylint: disable=unused-argument
        dry_run: Optional[str] = None,  # pylint: disable=unused-argument
        field_manager: Optional[str] = None,  # pylint: disable=unused-argument
        field_validation: Optional[str] = None,  # pylint: disable=unused-argument
        force: Optional[bool] = None,  # pylint: disable=unused-argument
        **_kwargs,
    ) -> k8s_client.V1Deployment:
        """Patch a specific deployment.

        Args:
            name: The name of the deployment to patch.
            namespace: The namespace of the deployment to patch.
            body: The patch to apply (can be a dict or V1Deployment).
            pretty: If 'true', output the pretty printed form of the object.
            dry_run: When present, indicates that modifications should not be persisted.
            field_manager: Field manager is associated with fields being applied.
            field_validation: Field validation mode.
            force: Force apply the patch. Defaults to false.

        Returns:
            The patched deployment.
        """
        # Get the existing deployment
        deployment = self.state.get_resource(namespace, "Deployment", name)

        # Apply the patch
        if isinstance(body, dict):
            # Handle dict-based patches
            patched_deployment = self._apply_patch(deployment, body)
        elif hasattr(body, "to_dict"):
            # Handle V1Deployment objects
            body_dict = body.to_dict()
            patched_deployment = self._apply_patch(deployment, body_dict)
        else:
            # Use as-is
            patched_deployment = body

        # Update the resource in state
        return self.state.update_resource(
            namespace, "Deployment", name, patched_deployment
        )

    def _apply_patch(self, deployment: Any, patch: Dict[str, Any]) -> Any:
        """Apply a patch to a deployment.

        Args:
            deployment: The original deployment.
            patch: The patch to apply (dict format).

        Returns:
            The patched deployment object.
        """
        # Apply patch directly to the deployment object
        self._apply_dict_to_object(deployment, patch)
        return deployment

    def _apply_dict_to_object(self, obj: Any, patch: Dict[str, Any]) -> None:
        """Recursively apply a dict patch to an object.

        Args:
            obj: The object to patch.
            patch: The patch dict to apply.
        """
        for key, value in patch.items():
            if value is None:
                continue

            # Handle dict objects (like labels, annotations) specially
            if isinstance(obj, dict):
                if isinstance(value, dict):
                    # Merge dict patches
                    obj[key] = {**obj.get(key, {}), **value}
                else:
                    obj[key] = value
                continue

            # Get the current value
            current_value = getattr(obj, key, None)

            if isinstance(value, dict) and current_value is not None:
                # Recursively patch nested dicts
                self._apply_dict_to_object(current_value, value)
            else:
                # Set the new value directly
                setattr(obj, key, value)

    def _deep_merge(
        self, base: Dict[str, Any], patch: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recursively merge patch into base dict.

        Args:
            base: The base dictionary.
            patch: The patch dictionary to merge.

        Returns:
            The merged dictionary.
        """
        result = base.copy()

        for key, value in patch.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value

        return result

    def _dict_to_v1_deployment(self, data: Dict[str, Any]) -> k8s_client.V1Deployment:
        """Convert a dict to a V1Deployment object.

        Args:
            data: Dictionary containing deployment data.

        Returns:
            A V1Deployment object.
        """
        # Extract metadata
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            metadata = k8s_client.V1ObjectMeta(
                **{k: v for k, v in metadata.items() if v is not None}
            )

        # Extract spec
        spec = data.get("spec", {})
        if isinstance(spec, dict):
            spec = k8s_client.V1DeploymentSpec(
                **{k: v for k, v in spec.items() if v is not None}
            )

        # Extract status
        status = data.get("status", {})
        if isinstance(status, dict):
            status = k8s_client.V1DeploymentStatus(
                **{k: v for k, v in status.items() if v is not None}
            )

        return k8s_client.V1Deployment(
            metadata=metadata,
            spec=spec,
            status=status,
        )

    def _simulate_deployment_controller(
        self, deployment: k8s_client.V1Deployment, namespace: str
    ) -> None:
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
                    labels=(
                        deployment.spec.template.metadata.labels.copy()
                        if deployment.spec.template.metadata.labels
                        else {}
                    ),
                    owner_references=[
                        k8s_client.V1OwnerReference(
                            api_version="apps/v1",
                            kind="Deployment",
                            name=deployment.metadata.name,
                            uid=deployment.metadata.uid,
                        )
                    ],
                ),
                spec=deployment.spec.template.spec,
                status=k8s_client.V1PodStatus(phase="Pending"),
            )

            # Add runtime_id label if present in deployment
            if (
                deployment.metadata.labels
                and "runtime_id" in deployment.metadata.labels
            ):
                if not pod.metadata.labels:
                    pod.metadata.labels = {}
                pod.metadata.labels["runtime_id"] = deployment.metadata.labels[
                    "runtime_id"
                ]

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
        self.state = state or (
            api_client.state if hasattr(api_client, "state") else MockKubernetesState()
        )

    def create_namespaced_ingress(
        self, namespace: str, body: k8s_client.V1Ingress, **_kwargs
    ) -> k8s_client.V1Ingress:
        """Create an ingress."""
        return self.state.create_resource(namespace, "Ingress", body)

    def read_namespaced_ingress(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Ingress:
        """Read a specific ingress."""
        return self.state.get_resource(namespace, "Ingress", name)

    def delete_namespaced_ingress(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
        """Delete an ingress."""
        self.state.delete_resource(namespace, "Ingress", name)
        return k8s_client.V1Status(status="Success")


class MockPolicyV1Api:
    """Mock implementation of kubernetes.client.PolicyV1Api."""

    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (
            api_client.state if hasattr(api_client, "state") else MockKubernetesState()
        )

    def create_namespaced_pod_disruption_budget(
        self, namespace: str, body: k8s_client.V1PodDisruptionBudget, **_kwargs
    ) -> k8s_client.V1PodDisruptionBudget:
        """Create a PodDisruptionBudget."""
        return self.state.create_resource(namespace, "PodDisruptionBudget", body)

    def read_namespaced_pod_disruption_budget(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1PodDisruptionBudget:
        """Read a specific PodDisruptionBudget."""
        return self.state.get_resource(namespace, "PodDisruptionBudget", name)

    def delete_namespaced_pod_disruption_budget(
        self, name: str, namespace: str, **_kwargs
    ) -> k8s_client.V1Status:
        """Delete a PodDisruptionBudget."""
        self.state.delete_resource(namespace, "PodDisruptionBudget", name)
        return k8s_client.V1Status(status="Success")


class MockCustomObjectsApi:
    """Mock implementation of kubernetes.client.CustomObjectsApi."""

    def __init__(self, api_client=None, state: Optional[MockKubernetesState] = None):
        self.api_client = api_client
        self.state = state or (
            api_client.state if hasattr(api_client, "state") else MockKubernetesState()
        )

    def create_namespaced_custom_object(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        body: Dict[str, Any],
        **_kwargs,
    ) -> Dict[str, Any]:
        """Create a custom resource."""
        kind = plural.capitalize().rstrip("s")  # Simple pluralization reversal

        # Convert dict to a simple object for storage
        class CustomResource:
            """Simple wrapper for custom resource data."""

            def __init__(self, data):
                self.__dict__.update(data)
                if "metadata" in data:
                    self.metadata = k8s_client.V1ObjectMeta(**data["metadata"])

            def to_dict(self):
                """Convert back to dictionary format."""
                return self.__dict__

            def get_name(self):
                """Get the resource name from metadata."""
                return (
                    self.metadata.name
                    if hasattr(self, "metadata") and self.metadata
                    else None
                )

        resource = CustomResource(body)
        self.state.create_resource(namespace, f"{group}/{version}/{kind}", resource)

        # Return as dict
        return body

    def get_namespaced_custom_object(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        **_kwargs,
    ) -> Dict[str, Any]:
        """Get a custom resource."""
        kind = plural.capitalize().rstrip("s")
        resource = self.state.get_resource(namespace, f"{group}/{version}/{kind}", name)

        # Convert back to dict format
        result = resource.__dict__.copy()

        # Convert metadata back to dict if it's a V1ObjectMeta
        if hasattr(resource, "metadata") and hasattr(resource.metadata, "name"):
            result["metadata"] = {
                "name": resource.metadata.name,
                "namespace": resource.metadata.namespace,
                "uid": resource.metadata.uid,
                "labels": resource.metadata.labels or {},
                "annotations": resource.metadata.annotations or {},
            }

        return result

    def delete_namespaced_custom_object(  # pylint: disable=too-many-arguments,too-many-positional-arguments
        self,
        group: str,
        version: str,
        namespace: str,
        plural: str,
        name: str,
        **_kwargs,
    ) -> Dict[str, Any]:
        """Delete a custom resource."""
        kind = plural.capitalize().rstrip("s")
        self.state.delete_resource(namespace, f"{group}/{version}/{kind}", name)
        return {"status": "Success"}
