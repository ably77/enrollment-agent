import subprocess


def run_kubectl(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    """Execute a kubectl command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr
