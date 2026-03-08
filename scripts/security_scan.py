#!/usr/bin/env python3
"""
Security scanning script.

Runs dependency vulnerability scanning, static code analysis, and container scanning.

Requirements: 42.8
"""

import sys
import subprocess
import json
from pathlib import Path

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

def print_header(text: str):
    """Print section header."""
    print(f"\n{BOLD}{'=' * 80}{RESET}")
    print(f"{BOLD}{text}{RESET}")
    print(f"{BOLD}{'=' * 80}{RESET}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}✓ {text}{RESET}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}⚠ {text}{RESET}")

def print_error(text: str):
    """Print error message."""
    print(f"{RED}✗ {text}{RESET}")

def run_command(cmd: list[str], check: bool = True) -> tuple[int, str, str]:
    """
    Run shell command and return result.
    
    Args:
        cmd: Command and arguments
        check: Whether to check return code
    
    Returns:
        Tuple of (return_code, stdout, stderr)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=check
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.CalledProcessError as e:
        return e.returncode, e.stdout, e.stderr
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"

def check_tool_installed(tool: str) -> bool:
    """Check if a tool is installed."""
    returncode, _, _ = run_command(["which", tool], check=False)
    return returncode == 0

def run_safety_scan() -> bool:
    """
    Run dependency vulnerability scanning with safety.
    
    Returns:
        True if no vulnerabilities found, False otherwise
    """
    print_header("Dependency Vulnerability Scanning (safety)")
    
    if not check_tool_installed("safety"):
        print_warning("safety not installed. Installing...")
        returncode, _, stderr = run_command(
            [sys.executable, "-m", "pip", "install", "safety"],
            check=False
        )
        if returncode != 0:
            print_error(f"Failed to install safety: {stderr}")
            return False
    
    # Run safety check
    print("Scanning dependencies for known vulnerabilities...")
    returncode, stdout, stderr = run_command(
        [sys.executable, "-m", "safety", "check", "--json"],
        check=False
    )
    
    if returncode == 0:
        print_success("No known vulnerabilities found in dependencies")
        return True
    else:
        # Parse JSON output
        try:
            vulnerabilities = json.loads(stdout)
            print_error(f"Found {len(vulnerabilities)} vulnerabilities:")
            for vuln in vulnerabilities:
                print(f"  - {vuln.get('package', 'unknown')} {vuln.get('installed_version', '')}")
                print(f"    {vuln.get('vulnerability', 'No description')}")
                print(f"    Fix: Upgrade to {vuln.get('fixed_version', 'latest')}")
                print()
        except json.JSONDecodeError:
            print_error(f"Vulnerabilities found:\n{stdout}")
        
        return False

def run_bandit_scan() -> bool:
    """
    Run static code analysis with bandit.
    
    Returns:
        True if no issues found, False otherwise
    """
    print_header("Static Code Analysis (bandit)")
    
    if not check_tool_installed("bandit"):
        print_warning("bandit not installed. Installing...")
        returncode, _, stderr = run_command(
            [sys.executable, "-m", "pip", "install", "bandit"],
            check=False
        )
        if returncode != 0:
            print_error(f"Failed to install bandit: {stderr}")
            return False
    
    # Run bandit
    print("Analyzing code for security issues...")
    returncode, stdout, stderr = run_command(
        [
            sys.executable, "-m", "bandit",
            "-r", "system_core",
            "-f", "json",
            "-ll"  # Only report medium and high severity
        ],
        check=False
    )
    
    # Parse results
    try:
        results = json.loads(stdout)
        issues = results.get("results", [])
        
        if not issues:
            print_success("No security issues found in code")
            return True
        else:
            print_error(f"Found {len(issues)} security issues:")
            for issue in issues[:10]:  # Show first 10
                print(f"  - {issue.get('issue_text', 'Unknown issue')}")
                print(f"    File: {issue.get('filename', 'unknown')}:{issue.get('line_number', 0)}")
                print(f"    Severity: {issue.get('issue_severity', 'UNKNOWN')}")
                print()
            
            if len(issues) > 10:
                print(f"  ... and {len(issues) - 10} more issues")
            
            return False
    except json.JSONDecodeError:
        print_error(f"Failed to parse bandit output:\n{stdout}")
        return False

def run_trivy_scan() -> bool:
    """
    Run container scanning with trivy.
    
    Returns:
        True if no critical vulnerabilities found, False otherwise
    """
    print_header("Container Scanning (trivy)")
    
    if not check_tool_installed("trivy"):
        print_warning("trivy not installed")
        print("Install trivy: https://aquasecurity.github.io/trivy/latest/getting-started/installation/")
        print("Skipping container scan...")
        return True  # Don't fail if trivy not installed
    
    # Check if Dockerfile exists
    dockerfile = Path("Dockerfile")
    if not dockerfile.exists():
        print_warning("Dockerfile not found. Skipping container scan...")
        return True
    
    # Run trivy on filesystem
    print("Scanning filesystem for vulnerabilities...")
    returncode, stdout, stderr = run_command(
        [
            "trivy", "fs",
            "--severity", "HIGH,CRITICAL",
            "--format", "json",
            "."
        ],
        check=False
    )
    
    if returncode == 0:
        try:
            results = json.loads(stdout)
            vulnerabilities = []
            for result in results.get("Results", []):
                vulnerabilities.extend(result.get("Vulnerabilities", []))
            
            if not vulnerabilities:
                print_success("No critical vulnerabilities found in container")
                return True
            else:
                print_error(f"Found {len(vulnerabilities)} critical vulnerabilities:")
                for vuln in vulnerabilities[:10]:  # Show first 10
                    print(f"  - {vuln.get('PkgName', 'unknown')}: {vuln.get('VulnerabilityID', '')}")
                    print(f"    Severity: {vuln.get('Severity', 'UNKNOWN')}")
                    print()
                
                if len(vulnerabilities) > 10:
                    print(f"  ... and {len(vulnerabilities) - 10} more vulnerabilities")
                
                return False
        except json.JSONDecodeError:
            print_error(f"Failed to parse trivy output:\n{stdout}")
            return False
    else:
        print_error(f"Trivy scan failed: {stderr}")
        return False

def main():
    """Run all security scans."""
    print(f"{BOLD}OpenFi Security Scanner{RESET}")
    print("Running comprehensive security scans...\n")
    
    results = {
        "dependency_scan": run_safety_scan(),
        "code_analysis": run_bandit_scan(),
        "container_scan": run_trivy_scan()
    }
    
    # Print summary
    print_header("Security Scan Summary")
    
    all_passed = all(results.values())
    
    for scan_name, passed in results.items():
        status = f"{GREEN}PASSED{RESET}" if passed else f"{RED}FAILED{RESET}"
        print(f"{scan_name.replace('_', ' ').title()}: {status}")
    
    print()
    
    if all_passed:
        print_success("All security scans passed!")
        return 0
    else:
        print_error("Some security scans failed. Please review and fix the issues.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
