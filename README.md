# SRE CLI for Kubernetes

![example](example.gif)

## Overview
SRE CLI is a command-line tool for managing and diagnosing Kubernetes deployments. It provides functionality to list deployments, scale them, retrieve deployment details, and diagnose issues within a cluster. Logging can be enabled with `--log` to capture execution details.

## Features
- 📋 **List** all deployments in a namespace or across all namespaces.
- 📌 **Scale** a deployment to a specific number of replicas.
- 🧐 **Retrieve Information** about a deployment including replica counts, labels, and annotations.
- 🔍 **Diagnose** a deployment, including pod-level diagnostics.
- 📝 **Logging Support**: Enable detailed logging with `--log`.

## Installation
### Prerequisites
- Python 3.7+
- `pip install -r requirements.txt`
- Kubernetes cluster (Minikube, AKS, EKS, GKE, etc.)
- `kubectl` configured with access to the cluster

### Clone the Repository
```sh
$ git clone https://github.com/adibnaya/sre-k8s-tool.git
$ cd sre-k8s-tool
```

### Install Dependencies
```sh
$ pip install -r requirements.txt
```

## Usage
Run the CLI tool with one of the available commands:

### List Deployments
```sh
$ python sre.py list --namespace=default
```

### Scale a Deployment
```sh
$ python sre.py scale --deployment=my-deployment --replicas=5 --namespace=default
```

### Get Deployment Info
```sh
$ python sre.py info --deployment=my-deployment --namespace=default
```

### Diagnose a Deployment
```sh
$ python sre.py diagnostic --deployment=my-deployment --namespace=default --pod
```

### Enable Logging
To enable logging and store logs in `sre_cli.log`, add `--log` before the name of the command:
```sh
$ python sre.py --log info --deployment=my-deployment
```

## Logging Behavior
- By default, logging is **disabled**.
- Use `--log` to enable logging (writes to `sre_cli.log` and prints logs to the console).
- Errors are always displayed in the console even without logging enabled.

## Configuration
- Ensure `~/.kube/config` is properly set up for cluster access.
- Modify `LOG_FILE` in `sre.py` to change the log file location.

## Troubleshooting
**Error: Connection Refused to Kubernetes API**
- Ensure your cluster is running (`kubectl cluster-info`)
- Check that your `~/.kube/config` is configured properly

**Unexpected Errors in Commands**
- Run with `--log` to capture error details
- Validate `kubectl get deployments -A` to confirm deployment exists

## License
This project is licensed under the MIT License. See `LICENSE` for details.

## Contact
For issues or suggestions, open a GitHub Issue or reach out via email at `adibnaya@gmail.com`.

