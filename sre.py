import argparse
import logging
import sys
from kube_utils import list_deployments, scale_deployment, get_deployment_info, diagnose_deployment

# Global variable to enable or disable logging
LOG_MODE = "--log" in sys.argv

# Logging setup (Only logs if log mode is enabled)
LOG_FILE = "sre_cli.log"
if LOG_MODE:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout)
        ]
    )


def prompt_for_input(param_name):
    """Prompt the user for missing input and return the value or exit gracefully."""
    user_input = input(f"Please enter a value for '{param_name}': ").strip()
    if not user_input:
        print(f"❌ No input provided for '{param_name}'. Exiting.")
        sys.exit(0)
    return user_input


def precheck_args():
    """Manually check for missing required arguments before argparse validation."""

    # ✅ If -h or --help is in the command, skip checks to allow argparse to show help
    if any(arg in ["-h", "--help"] for arg in sys.argv):
        return

    if len(sys.argv) < 2:  # No command provided
        print("❌ No command provided. Use -h for help.")
        sys.exit(0)

    command = sys.argv[1]

    def is_param_present(param):
        """Check if a param exists in sys.argv, even if given as --param=value"""
        return any(arg.startswith(f"--{param}=") or arg == f"--{param}" for arg in sys.argv)

    missing_params = []

    if command in ["scale", "info", "diagnostic"]:
        if not is_param_present("deployment"):
            missing_params.append("deployment")

    if command == "scale" and not is_param_present("replicas"):
        missing_params.append("replicas")

    # Prompt for missing params
    for param in missing_params:
        value = prompt_for_input(param)
        sys.argv.append(f"--{param}")
        sys.argv.append(value)


def main():
    precheck_args()  # ✅ Run manual checks first

    parser = argparse.ArgumentParser(description="SRE CLI for Kubernetes")
    parser.add_argument("--log", action="store_true", help="Enable logging (logs to file and prints logs)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # List Deployments
    list_parser = subparsers.add_parser("list", help="List deployments")
    list_parser.add_argument("--namespace", help="Namespace to list deployments from")

    # Scale Deployment
    scale_parser = subparsers.add_parser("scale", help="Scale a deployment")
    scale_parser.add_argument("--deployment", required=True, help="Deployment name")
    scale_parser.add_argument("--replicas", required=True, type=int, help="Number of replicas")
    scale_parser.add_argument("--namespace", help="Namespace of the deployment")

    # Get Deployment Info
    info_parser = subparsers.add_parser("info", help="Get deployment details")
    info_parser.add_argument("--deployment", required=True, help="Deployment name")
    info_parser.add_argument("--namespace", help="Namespace of the deployment")

    # Diagnose Deployment
    diagnostic_parser = subparsers.add_parser("diagnostic", help="Diagnose deployment")
    diagnostic_parser.add_argument("--deployment", required=True, help="Deployment name")
    diagnostic_parser.add_argument("--namespace", help="Namespace of the deployment")
    diagnostic_parser.add_argument("--pod", help="Get detailed pod diagnostics", action="store_true")

    # Parse arguments
    args = parser.parse_args()

    # Execute the corresponding function
    if LOG_MODE:
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
        if LOG_MODE:
            logging.error(f"Unexpected error: {e}", exc_info=True)
        else:
            print(f"❌ Unexpected error: {e}")


if __name__ == "__main__":
    main()
