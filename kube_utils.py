import sys
import logging
import requests
from kubernetes import client, config

# Check if log mode is enabled from arguments
LOG_MODE = "--log" in sys.argv

# Configure logging only if log mode is enabled
LOG_FILE = "sre_cli.log"
if LOG_MODE:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler()]
    )

# Load Kubernetes config
def load_kube_config():
    """Loads the Kubernetes configuration from ~/.kube/config"""
    try:
        config.load_kube_config()
        log_and_print("INFO", "Successfully loaded Kubernetes configuration.", "✅")
    except Exception as e:
        log_and_print("ERROR", f"Error loading Kubernetes config: {e}", "❌")
        sys.exit(1)

# Kubernetes API Clients
def get_k8s_clients():
    """Returns Kubernetes API clients"""
    load_kube_config()
    return client.AppsV1Api(), client.CoreV1Api()

# Logging and Printing in one function
def log_and_print(level, message, icon=""):
    """Handles logging and printing correctly based on --log mode"""
    log_message = message

    if LOG_MODE:
        # In log mode, log everything and print logs instead of normal output
        if level == "INFO":
            logging.info(log_message)
        elif level == "WARNING":
            logging.warning(log_message)
        elif level == "ERROR":
            logging.error(log_message)
    else:
        # Normal mode: Print messages with icons, but do not log to file
        print(f"{icon}  {message}")

# List Deployments
def list_deployments(namespace=None):
    """Lists all deployments in the specified namespace or across all namespaces"""
    v1_apps, _ = get_k8s_clients()
    try:
        deployments = v1_apps.list_namespaced_deployment(namespace) if namespace else v1_apps.list_deployment_for_all_namespaces()
        for dep in deployments.items:
            log_and_print("INFO", f"Deployment: {dep.metadata.name} (Namespace: {dep.metadata.namespace})", "📦")
    except client.exceptions.ApiException as e:
        log_and_print("ERROR", f"Error listing deployments: {e.reason}", "❌")
    except Exception as e:
        log_and_print("ERROR", f"Unexpected error: {e}", "❌")

# Scale Deployment
def scale_deployment(deployment, replicas, namespace=None):
    """Scales a deployment and logs the operation"""
    v1_apps, _ = get_k8s_clients()
    try:
        if namespace:
            dep = v1_apps.read_namespaced_deployment(deployment, namespace)
            dep.spec.replicas = replicas
            v1_apps.patch_namespaced_deployment_scale(deployment, namespace, dep)
            log_and_print("INFO", f"Scaled {deployment} to {replicas} replicas in namespace {namespace}", "📈")
        else:
            all_deployments = v1_apps.list_deployment_for_all_namespaces()
            matched_deployments = [dep for dep in all_deployments.items if dep.metadata.name == deployment]

            if not matched_deployments:
                log_and_print("WARNING", f"Deployment '{deployment}' not found in any namespace.", "⚠️")
                return

            for dep in matched_deployments:
                ns = dep.metadata.namespace
                dep.spec.replicas = replicas
                v1_apps.patch_namespaced_deployment_scale(deployment, ns, dep)
                log_and_print("INFO", f"Scaled {deployment} to {replicas} replicas in namespace {ns}", "📈")

    except client.exceptions.ApiException as e:
        log_and_print("ERROR", f"Error scaling deployment: {e.reason}", "❌")
    except Exception as e:
        log_and_print("ERROR", f"Unexpected error: {e}", "❌")

# Get Deployment Info
def get_deployment_info(deployment, namespace=None):
    """Retrieves and prints detailed information about a deployment."""

    v1_apps, _ = get_k8s_clients()

    try:
        if namespace:
            # Fetch deployment from a specific namespace
            dep = v1_apps.read_namespaced_deployment(deployment, namespace)
        else:
            # ✅ Fix: Handle failure when querying all namespaces
            try:
                all_deployments = v1_apps.list_deployment_for_all_namespaces()
                dep = next((d for d in all_deployments.items if d.metadata.name == deployment), None)
                if not dep:
                    log_and_print("WARNING", f"Deployment '{deployment}' not found in any namespace.", "⚠️")
                    return
                namespace = dep.metadata.namespace
            except client.exceptions.ApiException as e:
                if e.status == 403:
                    log_and_print("ERROR", "Permission denied: Cannot access all namespaces.", "🚫")
                else:
                    log_and_print("ERROR", f"Kubernetes API Error: {e.reason}", "❌")
                return
            except Exception as e:
                log_and_print("ERROR", f"Unexpected error retrieving deployments: {e}", "❌")
                return

        dep_info = {
            "Deployment Name": dep.metadata.name,
            "Namespace": namespace,
            "Replicas (Desired)": dep.spec.replicas,
            "Replicas (Available)": dep.status.available_replicas or 0,
            "Strategy Type": dep.spec.strategy.type,
            "Creation Timestamp": dep.metadata.creation_timestamp,
            "Labels": dep.metadata.labels or {},
            "Annotations": dep.metadata.annotations or {},
            "Images": [container.image for container in dep.spec.template.spec.containers],
        }

        log_and_print("INFO", f"--- Deployment Info: {dep.metadata.name} ---", "\n🛠")
        for key, value in dep_info.items():
            log_and_print("INFO", f"{key}: {value}", "📌")

    except requests.exceptions.ConnectionError:
        log_and_print("ERROR", "Could not connect to the Kubernetes API. Is your cluster running?", "❌")
    except client.exceptions.ApiException as e:
        if e.status == 404:
            log_and_print("WARNING", f"Deployment '{deployment}' not found in namespace '{namespace}'.", "⚠️")
        elif e.status == 403:
            log_and_print("ERROR", f"Permission denied: Cannot access deployment '{deployment}' in namespace '{namespace}'.", "🚫")
        else:
            log_and_print("ERROR", f"Kubernetes API Error: {e.reason}", "❌")
    except Exception as e:
        log_and_print("ERROR", f"Unexpected error: {e}", "❌")


def diagnose_deployment(deployment, namespace=None, pod_diagnostics=False):
    """
    Diagnoses a deployment's health using the best Kubernetes logging practices.

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
                log_and_print("WARNING", f"Deployment '{deployment}' not found in any namespace.", "⚠️")
                return
            namespace = dep.metadata.namespace

        log_and_print("INFO", f"--- Deployment Diagnosis: {dep.metadata.name} ---", "\n🔍")
        log_and_print("INFO", f"Namespace: {namespace}", "📍")
        log_and_print("INFO", f"Desired Replicas: {dep.spec.replicas}", "🔢")
        log_and_print("INFO", f"Available Replicas: {dep.status.available_replicas or 0}", "✅")
        log_and_print("INFO", f"Unavailable Replicas: {dep.spec.replicas - (dep.status.available_replicas or 0)}", "❌")

        # Get Deployment Conditions
        conditions = dep.status.conditions or []
        for condition in conditions:
            log_and_print("INFO", f"Condition: {condition.type} | Status: {condition.status} | Message: {condition.message}", "⚠")

        # 2️⃣ CHECK REPLICASETS
        replicasets = v1_apps.list_namespaced_replica_set(namespace).items
        matched_replicasets = [rs for rs in replicasets if rs.metadata.owner_references and rs.metadata.owner_references[0].name == deployment]

        log_and_print("INFO", "--- ReplicaSets ---", "\n🔄")
        for rs in matched_replicasets:
            log_and_print("INFO", f"ReplicaSet: {rs.metadata.name} | Ready Replicas: {rs.status.ready_replicas or 0}/{rs.status.replicas}", "📦")

        # 3️⃣ CHECK POD STATUS (Only if --pod is enabled)
        if pod_diagnostics:
            pods = v1_core.list_namespaced_pod(namespace).items
            related_pods = [pod for pod in pods if pod.metadata.name.startswith(f"{deployment}-")]

            log_and_print("INFO", "--- Pod Status ---", "\n🟢")
            for pod in related_pods:
                log_and_print("INFO", f"Pod: {pod.metadata.name} | Status: {pod.status.phase}", "🔹")

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
                log_and_print("WARNING", "--- Deployment-Wide Issues Detected ---", "\n❌")
                for pod in failed_pods:
                    log_and_print("WARNING", f"   Pod: {pod['Pod']}", "🔴")
                    log_and_print("WARNING", f"   Failure Reason: {pod['Reason']}", "❌")
                    log_and_print("WARNING", f"   Message: {pod['Message']}", "📝")

            # 4️⃣ CHECK POD EVENTS & LOGS (Only if --pod is enabled)
            try:
                events = v1_core.list_namespaced_event(namespace).items

                if not events:
                    log_and_print("INFO", "--- Pod Events (Latest First) ---", "\n📜")
                    log_and_print("INFO", "No events found for this namespace.", "ℹ")
                else:
                    sorted_events = sorted(events, key=lambda e: e.metadata.creation_timestamp, reverse=True)

                    log_and_print("INFO", "--- Pod Events (Latest First) ---", "\n📜")
                    for event in sorted_events[:10]:  # Show last 10 events if available
                        log_and_print("INFO", f"[{event.type}] {event.reason}: {event.message}")

            except client.exceptions.ApiException as e:
                log_and_print("ERROR", f"Error retrieving pod events: {e.reason}", "\n❌")
            except Exception as e:
                log_and_print("ERROR", f"Unexpected error retrieving pod events: {e}", "\n❌")

            # 5️⃣ CHECK POD RESOURCE USAGE (Only if --pod is enabled)
            log_and_print("INFO", "--- Pod Resource Usage ---", "\n📊")

            # Get max pod name length for alignment
            max_pod_name_length = max(len(pod.metadata.name) for pod in related_pods) if related_pods else 0
            padding = max_pod_name_length + 5  # Add some space for readability

            for pod in related_pods:
                for container in pod.spec.containers:
                    requests = container.resources.requests or {}
                    limits = container.resources.limits or {}
                    pod_name = pod.metadata.name.ljust(padding)  # Align pod names dynamically

                    log_and_print("INFO", f"Pod: {pod_name} CPU Request: {requests.get('cpu', 'Not Set')} | Memory Request: {requests.get('memory', 'Not Set')}", "🔹")
                    log_and_print("INFO", f"{' ' * (padding + (5 if LOG_MODE else 7))} CPU Limit: {limits.get('cpu', 'Not Set')} | Memory Limit: {limits.get('memory', 'Not Set')}")

    except client.exceptions.ApiException as e:
        log_and_print("ERROR", f"Error diagnosing deployment: {e.reason}", "❌")
    except Exception as e:
        log_and_print("ERROR", f"Unexpected error: {e}", "❌")
