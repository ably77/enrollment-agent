import subprocess

import streamlit as st


def run_kubectl(cmd: str, timeout: int = 120) -> tuple[int, str, str]:
    """Execute a kubectl command and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


def cleanup_ok(rc: int, stderr: str) -> bool:
    """Return True if a cleanup command succeeded or the resource was already gone."""
    return rc == 0 or "NotFound" in stderr or "not found" in stderr


def render_kubectl(rc: int, stdout: str, stderr: str) -> None:
    """Display kubectl command output with appropriate formatting."""
    if stdout.strip():
        st.code(stdout, language="text")
    if rc != 0 and stderr.strip():
        st.error(stderr)
    elif stderr.strip():
        st.caption(stderr)
