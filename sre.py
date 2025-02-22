import argparse
import logging
import sys
from kube_utils import list_deployments, scale_deployment, get_deployment_info, diagnose_deployment

# Logging setup
LOG_FILE = "sre_cli.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),  # Log file supports UTF-8
        logging.StreamHandler(sys.stdout)  # Force UTF-8 output in console
    ]
)


def main():
    parser = argparse.ArgumentParser(description="SRE CLI for Kubernetes")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List Deployments
    list_parser = subparsers.add_parser("list", help="List deployments")
    list_parser.add_argument("--namespace", help="Namespace to list deployments from", default=None)

    # Scale Deployment
    scale_parser = subparsers.add_parser("scale", help="Scale a deployment")
    scale_parser.add_argument("--deployment", required=True, help="Deployment name")
    scale_parser.add_argument("--replicas", required=True, type=int, help="Number of replicas")
    scale_parser.add_argument("--namespace", help="Namespace of the deployment", default=None)

    # Get Deployment Info
    info_parser = subparsers.add_parser("info", help="Get deployment details")
    info_parser.add_argument("--deployment", required=True, help="Deployment name")
    info_parser.add_argument("--namespace", help="Namespace of the deployment", default=None)

    # Diagnose Deployment
    diagnostic_parser = subparsers.add_parser("diagnostic", help="Diagnose deployment")
    diagnostic_parser.add_argument("--deployment", required=True, help="Deployment name")
    diagnostic_parser.add_argument("--namespace", help="Namespace of the deployment", default=None)
    diagnostic_parser.add_argument("--pod", help="Get detailed pod diagnostics", action="store_true")

    # Parse arguments
    args = parser.parse_args()

    # Execute the corresponding function
    logging.info(f"Executing command: {args.command} with args: {args}")

    try:
        if args.command == "list":
            list_deployments(args.namespace)
        elif args.command == "scale":
            scale_deployment(args.deployment, args.replicas, args.namespace)
        elif args.command == "info":
            get_deployment_info(args.deployment, args.namespace)
        elif args.command == "diagnostic":
            diagnose_deployment(args.deployment, args.namespace, args.pod)
        else:
            parser.print_help()
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
