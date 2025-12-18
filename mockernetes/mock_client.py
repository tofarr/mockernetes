"""
Mock Kubernetes API Client - Drop-in replacement for kubernetes.client.ApiClient

This module provides a stateful mock implementation that can replace the real
Kubernetes API client in tests, maintaining resource state and relationships.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kubernetes import client as k8s_client
from kubernetes.client.rest import ApiException


class MockKubernetesState:
    """Manages the state of all Kubernetes resources in the mock cluster."""

    def __init__(self):
        # Organize resources by namespace and kind
        self.namespaces: Dict[str, Dict[str, Dict[str, Any]]] = {}
        self.cluster_resources: Dict[str, Dict[str, Any]] = (
            {}
        )  # For cluster-scoped resources
        self.events: List[Dict[str, Any]] = []

        # Create default namespace
        self.ensure_namespace("default")

    def ensure_namespace(self, namespace: str) -> None:
        """Ensure a namespace exists in the state."""
        if namespace not in self.namespaces:
            self.namespaces[namespace] = {}

    def get_resource_store(self, namespace: Optional[str], kind: str) -> Dict[str, Any]:
        """Get the storage dict for a specific resource type."""
        if namespace is None:
            # Cluster-scoped resource
            if kind not in self.cluster_resources:
                self.cluster_resources[kind] = {}
            return self.cluster_resources[kind]
        # Namespaced resource
        self.ensure_namespace(namespace)
        if kind not in self.namespaces[namespace]:
            self.namespaces[namespace][kind] = {}
        return self.namespaces[namespace][kind]

    def create_resource(
        self, namespace: Optional[str], kind: str, resource: Any
    ) -> Any:
        """Store a new resource and return it with generated metadata."""
        store = self.get_resource_store(namespace, kind)

        # Generate metadata if not present
        if not hasattr(resource, "metadata") or resource.metadata is None:
            resource.metadata = k8s_client.V1ObjectMeta()

        if not resource.metadata.name:
            resource.metadata.name = f"{kind.lower()}-{uuid.uuid4().hex[:8]}"

        if not resource.metadata.uid:
            resource.metadata.uid = str(uuid.uuid4())

        if not resource.metadata.creation_timestamp:
            resource.metadata.creation_timestamp = datetime.now(timezone.utc)

        if namespace and not resource.metadata.namespace:
            resource.metadata.namespace = namespace

        # Check if resource already exists
        if resource.metadata.name in store:
            raise ApiException(status=409, reason="Conflict")

        # Store the resource
        store[resource.metadata.name] = resource

        # Generate creation event
        self._add_event(namespace, kind, resource.metadata.name, "Created")

        return resource

    def get_resource(self, namespace: Optional[str], kind: str, name: str) -> Any:
        """Retrieve a specific resource."""
        store = self.get_resource_store(namespace, kind)
        if name not in store:
            raise ApiException(status=404, reason="Not Found")
        return store[name]

    def list_resources(
        self, namespace: Optional[str], kind: str, label_selector: Optional[str] = None
    ) -> List[Any]:
        """List resources, optionally filtered by label selector."""
        store = self.get_resource_store(namespace, kind)
        resources = list(store.values())

        if label_selector:
            resources = self._filter_by_labels(resources, label_selector)

        return resources

    def update_resource(
        self, namespace: Optional[str], kind: str, name: str, resource: Any
    ) -> Any:
        """Update an existing resource."""
        store = self.get_resource_store(namespace, kind)
        if name not in store:
            raise ApiException(status=404, reason="Not Found")

        # Preserve metadata
        existing = store[name]
        resource.metadata.uid = existing.metadata.uid
        resource.metadata.creation_timestamp = existing.metadata.creation_timestamp
        resource.metadata.namespace = existing.metadata.namespace

        store[name] = resource
        self._add_event(namespace, kind, name, "Updated")
        return resource

    def delete_resource(self, namespace: Optional[str], kind: str, name: str) -> None:
        """Delete a resource and handle owner references."""
        store = self.get_resource_store(namespace, kind)
        if name not in store:
            raise ApiException(status=404, reason="Not Found")

        resource = store[name]
        del store[name]

        # Handle cascading deletion via owner references
        if hasattr(resource, "metadata") and resource.metadata:
            self._cascade_delete(namespace, resource.metadata.uid)

        self._add_event(namespace, kind, name, "Deleted")

    def _filter_by_labels(self, resources: List[Any], label_selector: str) -> List[Any]:
        """Filter resources by label selector (simplified implementation)."""
        filtered = []

        # Parse simple label selectors like "key=value" or "key=value,key2=value2"
        selectors = {}
        for selector in label_selector.split(","):
            if "=" in selector:
                key, value = selector.split("=", 1)
                selectors[key.strip()] = value.strip()

        for resource in resources:
            if (
                hasattr(resource, "metadata")
                and resource.metadata
                and resource.metadata.labels
            ):
                match = True
                for key, value in selectors.items():
                    if resource.metadata.labels.get(key) != value:
                        match = False
                        break
                if match:
                    filtered.append(resource)

        return filtered

    def _cascade_delete(self, namespace: Optional[str], owner_uid: str) -> None:
        """Delete resources that have the given UID as an owner reference."""
        all_stores = self._get_all_stores(namespace)
        to_delete = self._find_dependent_resources(all_stores, owner_uid)
        self._delete_dependent_resources(to_delete)

    def _get_all_stores(self, namespace: Optional[str]) -> List[tuple]:
        """Get all resource stores to check for dependencies."""
        all_stores = []

        if namespace:
            # Check specific namespace
            for kind, store in self.namespaces.get(namespace, {}).items():
                all_stores.append((namespace, kind, store))
        else:
            # Check all namespaces
            for ns, kinds in self.namespaces.items():
                for kind, store in kinds.items():
                    all_stores.append((ns, kind, store))

        # Also check cluster-scoped resources
        for kind, store in self.cluster_resources.items():
            all_stores.append((None, kind, store))

        return all_stores

    def _find_dependent_resources(
        self, all_stores: List[tuple], owner_uid: str
    ) -> List[tuple]:
        """Find resources that depend on the given owner UID."""
        to_delete = []
        for ns, kind, store in all_stores:
            for name, resource in store.items():
                if self._has_owner_reference(resource, owner_uid):
                    to_delete.append((ns, kind, name))
        return to_delete

    def _has_owner_reference(self, resource: Any, owner_uid: str) -> bool:
        """Check if resource has the given UID as an owner reference."""
        if not (
            hasattr(resource, "metadata")
            and resource.metadata
            and resource.metadata.owner_references
        ):
            return False
        return any(
            owner_ref.uid == owner_uid
            for owner_ref in resource.metadata.owner_references
        )

    def _delete_dependent_resources(self, to_delete: List[tuple]) -> None:
        """Delete the list of dependent resources."""
        for ns, kind, name in to_delete:
            try:
                self.delete_resource(ns, kind, name)
            except ApiException:
                pass  # Resource might already be deleted

    def _add_event(
        self, namespace: Optional[str], kind: str, name: str, action: str
    ) -> None:
        """Add an event to the event log."""
        event = {
            "timestamp": datetime.now(timezone.utc),
            "namespace": namespace,
            "kind": kind,
            "name": name,
            "action": action,
        }
        self.events.append(event)

        # Keep only last 1000 events
        if len(self.events) > 1000:
            self.events = self.events[-1000:]


class MockApiClient:
    """Mock implementation of kubernetes.client.ApiClient."""

    def __init__(self, state: Optional[MockKubernetesState] = None):
        self.state = state or MockKubernetesState()
        self.configuration = k8s_client.Configuration()

    def call_api(self, *args, **kwargs):
        """Mock implementation of call_api - not typically used directly."""
        raise NotImplementedError(
            "Use specific API classes instead of call_api directly"
        )

    def close(self):
        """Mock close method."""

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
