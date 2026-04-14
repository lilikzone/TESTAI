"""
CLI Executor — Runs AWS CLI commands via subprocess.
Only accepts pre-validated commands from the pipeline.
Never called directly from routes.
"""

import shlex
import subprocess
from dataclasses import dataclass


@dataclass
class ExecuteResult:
    success: bool
    output: str
    error: str | None
    return_code: int


def run_cli(command: str) -> dict:
    """
    Execute an AWS CLI command and return a plain dict result.

    Args:
        command: Full AWS CLI command string (e.g. "aws s3 ls")

    Returns:
        dict with keys:
            success (bool)  — True if exit code is 0
            output  (str)   — stdout from the command
            error   (str)   — stderr or error message, empty string if none
    """
    if not command.startswith("aws "):
        return {
            "success": False,
            "output": "",
            "error": "Invalid command: only 'aws' CLI commands are permitted.",
        }

    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=10,
        )
        success = result.returncode == 0
        return {
            "success": success,
            "output": result.stdout.strip(),
            "error": result.stderr.strip() if not success else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "output": "",
            "error": "Command timed out after 10 seconds.",
        }
    except FileNotFoundError:
        return {
            "success": False,
            "output": "",
            "error": "AWS CLI is not installed or not found in PATH.",
        }
    except Exception as e:
        return {
            "success": False,
            "output": "",
            "error": f"Unexpected error: {str(e)}",
        }


def execute(command: str, timeout: int = 60) -> ExecuteResult:
    """
    Execute a validated AWS CLI command as a subprocess.

    Args:
        command: Full AWS CLI command string (e.g. "aws ec2 describe-instances ...")
        timeout: Max seconds to wait before killing the process

    Returns:
        ExecuteResult with stdout, stderr, and return code
    """
    if not command.startswith("aws "):
        return ExecuteResult(
            success=False,
            output="",
            error="Invalid command: only 'aws' CLI commands are permitted.",
            return_code=1,
        )

    try:
        args = shlex.split(command)
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        success = result.returncode == 0
        return ExecuteResult(
            success=success,
            output=result.stdout.strip(),
            error=result.stderr.strip() if not success else None,
            return_code=result.returncode,
        )
    except subprocess.TimeoutExpired:
        return ExecuteResult(
            success=False,
            output="",
            error=f"Command timed out after {timeout} seconds.",
            return_code=124,
        )
    except FileNotFoundError:
        return ExecuteResult(
            success=False,
            output="",
            error="AWS CLI is not installed or not found in PATH.",
            return_code=127,
        )
    except Exception as e:
        return ExecuteResult(
            success=False,
            output="",
            error=f"Unexpected error during execution: {str(e)}",
            return_code=1,
        )
