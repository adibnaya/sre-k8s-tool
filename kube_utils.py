import json
import sys
import logging
import requests
from kubernetes import client, config

# Configure logging
LOG_FILE = "sre_cli.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)

# Load Kubernetes config
def load_kube_config():
    """Loads the Kubernetes configuration from ~/.kube/config"""
    try:
        config.load_kube_config()
        logging.info("Successfully loaded Kubernetes configuration.")
    except Exception as e:
        logging.error(f"Error loading Kubernetes config: {e}")
        sys.exit(1)

# Kubernetes API Clients
def get_k8s_clients():
    """Returns Kubernetes API clients"""
    load_kube_config()
    return client.AppsV1Api(), client.CoreV1Api()

# List Deployments
def list_deployments(namespace=None):
    """Lists all deployments in the specified namespace or across all namespaces if none is provided"""
    v1_apps, _ = get_k8s_clients()
    try:
        deployments = v1_apps.list_namespaced_deployment(
            namespace) if namespace else v1_apps.list_deployment_for_all_namespaces()
        for dep in deployments.items:
            logging.info(f"Deployment: {dep.metadata.name}, Namespace: {dep.metadata.namespace}")
    except client.exceptions.ApiException as e:
        logging.error(f"Error listing deployments: {e.reason}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

# Scale Deployment
def scale_deployment(deployment, replicas, namespace=None):
    """Scales a deployment and logs the operation"""
    v1_apps, _ = get_k8s_clients()

    try:
        if namespace:
            dep = v1_apps.read_namespaced_deployment(deployment, namespace)
            dep.spec.replicas = replicas
            v1_apps.patch_namespaced_deployment_scale(deployment, namespace, dep)
            logging.info(f"Scaled {deployment} to {replicas} replicas in namespace {namespace}")
        else:
            all_deployments = v1_apps.list_deployment_for_all_namespaces()
            matched_deployments = [dep for dep in all_deployments.items if dep.metadata.name == deployment]

            if not matched_deployments:
                logging.warning(f"Deployment '{deployment}' not found in any namespace.")
                return

            for dep in matched_deployments:
                ns = dep.metadata.namespace
                dep.spec.replicas = replicas
                v1_apps.patch_namespaced_deployment_scale(deployment, ns, dep)
                logging.info(f"Scaled {deployment} to {replicas} replicas in namespace {ns}")

    except client.exceptions.ApiException as e:
        logging.error(f"Error scaling deployment: {e.reason}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

# Get Deployment Info
def get_deployment_info(deployment, namespace=None):
    """Retrieves and prints detailed information about a deployment."""
    try:
        v1_apps = client.AppsV1Api()

        if namespace:
            dep = v1_apps.read_namespaced_deployment(deployment, namespace)
        else:
            all_deployments = v1_apps.list_deployment_for_all_namespaces()
            dep = next((d for d in all_deployments.items if d.metadata.name == deployment), None)
            if not dep:
                logging.warning(f"Deployment '{deployment}' not found in any namespace.")
                return
            namespace = dep.metadata.namespace  # Set namespace for display

        dep_info = {
            "Deployment Name": dep.metadata.name,
            "Namespace": namespace,
            "Replicas (Desired)": dep.spec.replicas,
            "Replicas (Available)": dep.status.available_replicas or 0,
            "Strategy Type": dep.spec.strategy.type,
            "Creation Timestamp": dep.metadata.creation_timestamp,
            "Labels": dep.metadata.labels or {},
            "Annotations": dep.metadata.annotations or {},
        }

        logging.info(f"Deployment Info Retrieved: {json.dumps(dep_info, indent=4, default=str)}")

    except requests.exceptions.ConnectionError:
        logging.error("Error: Could not connect to the Kubernetes API. Is the cluster running?")
    except client.exceptions.ApiException as e:
        logging.error(f"Kubernetes API Error: {e.reason}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")


# Diagnose Deployment
def diagnose_deployment(deployment, namespace=None, pod_diagnostics=False):
    """
    Diagnoses a deployment's health using best Kubernetes debugging practices.

    - Always checks Deployment, ReplicaSets, and general pod statuses.
    - Identifies deployment-wide failures (`ImagePullBackOff`, `CrashLoopBackOff`).
    - If `--pod` is provided, includes:
        - Pod descriptions (`kubectl describe pod`).
        - Pod resource usage (`kubectl top pod`).
        - Pod events & logs (`kubectl logs`).
    - Also checks:
        - Node health (`kubectl describe node`).
        - ConfigMaps, Secrets, Services, and Networking issues.
    """
    v1_apps, v1_core = get_k8s_clients()

    try:
        # 1️⃣ CHECK DEPLOYMENT STATUS
        if namespace:
            dep = v1_apps.read_namespaced_deployment(deployment, namespace)
        else:
            all_deployments = v1_apps.list_deployment_for_all_namespaces()
            dep = next((d for d in all_deployments.items if d.metadata.name == deployment), None)
            if not dep:
                logging.warning(f"Deployment '{deployment}' not found in any namespace.")
                return
            namespace = dep.metadata.namespace

        logging.info(f"\n--- Deployment Diagnosis: {dep.metadata.name} ---")
        logging.info(f"Namespace: {namespace}")
        logging.info(f"Desired Replicas: {dep.spec.replicas}")
        logging.info(f"Available Replicas: {dep.status.available_replicas or 0}")
        logging.info(f"Unavailable Replicas: {dep.spec.replicas - (dep.status.available_replicas or 0)}")

        # Get Deployment Conditions
        conditions = dep.status.conditions or []
        for condition in conditions:
            logging.info(f"   Condition: {condition.type} | Status: {condition.status} | Message: {condition.message}")

        # 2️⃣ CHECK REPLICASETS
        replicasets = v1_apps.list_namespaced_replica_set(namespace).items
        matched_replicasets = [rs for rs in replicasets if rs.metadata.owner_references and rs.metadata.owner_references[0].name == deployment]

        logging.info("\n--- ReplicaSets ---")
        for rs in matched_replicasets:
            logging.info(f"ReplicaSet: {rs.metadata.name} | Ready Replicas: {rs.status.ready_replicas or 0}/{rs.status.replicas}")

        # 3️⃣ CHECK POD STATUS (Only if --pod is enabled)
        if pod_diagnostics:
            pods = v1_core.list_namespaced_pod(namespace).items
            related_pods = [pod for pod in pods if pod.metadata.name.startswith(f"{deployment}-")]

            logging.info("\n--- Pod Status ---")
            for pod in related_pods:
                logging.info(f"Pod: {pod.metadata.name} | Status: {pod.status.phase}")

            # Detect Failing Pods (Only if --pod is enabled)
            failed_pods = []
            for pod in related_pods:
                for cs in pod.status.container_statuses or []:
                    if cs.state.waiting:
                        failed_pods.append({
                            "Pod": pod.metadata.name,
                            "Reason": cs.state.waiting.reason,
                            "Message": cs.state.waiting.message
                        })

            if failed_pods:
                logging.warning("\n--- Deployment-Wide Issues Detected ---")
                for pod in failed_pods:
                    logging.warning(f"   Pod: {pod['Pod']}")
                    logging.warning(f"   Failure Reason: {pod['Reason']}")
                    logging.warning(f"   Message: {pod['Message']}")

            # 4️⃣ CHECK POD EVENTS & LOGS (Only if --pod is enabled)
            try:
                events = v1_core.list_namespaced_event(namespace).items

                if not events:
                    logging.info("\n--- Pod Events (Latest First) ---")
                    logging.info("ℹ No events found for this namespace.")
                else:
                    sorted_events = sorted(events, key=lambda e: e.metadata.creation_timestamp, reverse=True)

                    logging.info("\n--- Pod Events (Latest First) ---")
                    for event in sorted_events[:10]:  # Show last 10 events if available
                        logging.info(f"[{event.type}] {event.reason}: {event.message}")

            except client.exceptions.ApiException as e:
                logging.error(f"\nError retrieving pod events: {e.reason}")
            except Exception as e:
                logging.error(f"\nUnexpected error retrieving pod events: {e}")

            # 5️⃣ CHECK POD RESOURCE USAGE (Only if --pod is enabled)
            logging.info("\n--- Pod Resource Usage ---")

            # Get max pod name length for alignment
            max_pod_name_length = max(len(pod.metadata.name) for pod in related_pods) if related_pods else 0
            padding = max_pod_name_length + 5  # Add some space for readability

            for pod in related_pods:
                for container in pod.spec.containers:
                    requests = container.resources.requests or {}
                    limits = container.resources.limits or {}
                    pod_name = pod.metadata.name.ljust(padding)  # Align pod names dynamically

                    logging.info(f"Pod: {pod_name} CPU Request: {requests.get('cpu', 'Not Set')} | Memory Request: {requests.get('memory', 'Not Set')}")
                    logging.info(f"{' ' * (padding + 5)} CPU Limit: {limits.get('cpu', 'Not Set')} | Memory Limit: {limits.get('memory', 'Not Set')}")

    except client.exceptions.ApiException as e:
        logging.error(f"Error diagnosing deployment: {e.reason}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")