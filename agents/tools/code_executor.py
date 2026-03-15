"""
CodeExecutor — sandboxed Python + Docker command execution for autonomous agents.

Anti-hallucination gates:
  1. Syntax gate  : compile() before any execution
  2. Sandbox gate : subprocess only, never eval/exec in-process
  3. Sample gate  : run on ≤10 rows before full dataset
  4. Schema gate  : validate output type/shape after execution
  5. Timeout gate : hard kill after N seconds
"""
import os
import sys
import ast
import json
import time
import logging
import tempfile
import textwrap
import subprocess
from typing import Any

logger = logging.getLogger(__name__)

EXEC_TIMEOUT = int(os.getenv("CODE_EXEC_TIMEOUT", "45"))   # seconds


class CodeExecutionError(Exception):
    pass


class CodeExecutor:
    """Shared tool — import and use inside any agent."""

    # ------------------------------------------------------------------ #
    #  1. Python execution in a subprocess                                 #
    # ------------------------------------------------------------------ #
    def execute_python(
        self,
        code: str,
        timeout: int = EXEC_TIMEOUT,
        extra_env: dict = None,
        stdin_data: str = None,
    ) -> dict:
        """
        Execute Python code in an isolated subprocess.
        Returns: {ok, stdout, stderr, exit_code, duration_ms}
        Raises CodeExecutionError on syntax errors (before execution).
        """
        # Gate 1 — syntax check
        self._assert_syntax(code)

        env = {**os.environ, **(extra_env or {})}
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp = f.name

        t0 = time.time()
        try:
            result = subprocess.run(
                [sys.executable, tmp],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                # Bug 30: restrict working directory to /tmp for security
                cwd="/tmp",
            )
            duration = int((time.time() - t0) * 1000)
            ok = result.returncode == 0
            if not ok:
                logger.warning(f"[executor] exit={result.returncode} stderr={result.stderr[:300]}")
            return {
                "ok": ok,
                "stdout": result.stdout,
                # Bug 26: increase stderr truncation from 1000 to 4000 chars
                "stderr": result.stderr[:4000],
                "exit_code": result.returncode,
                "duration_ms": duration,
            }
        except subprocess.TimeoutExpired:
            # Bug 6: temp file must be cleaned up even on timeout
            raise CodeExecutionError(f"Execution timed out after {timeout}s")
        finally:
            # Bug 6: always attempt to clean up the temp file
            try:
                os.unlink(tmp)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  2. Execute code inside a Docker container                           #
    # ------------------------------------------------------------------ #
    def run_in_container(
        self,
        container: str,
        command: list,
        timeout: int = EXEC_TIMEOUT,
    ) -> dict:
        """
        Run a command inside a running Docker container.
        command: list of strings, e.g. ["python3", "-c", "print('hi')"]
        Returns: {ok, stdout, stderr, exit_code}
        """
        cmd = ["docker", "exec", container] + command
        t0 = time.time()
        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout
            )
            return {
                "ok": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr[:1000],
                "exit_code": result.returncode,
                "duration_ms": int((time.time() - t0) * 1000),
            }
        except subprocess.TimeoutExpired:
            raise CodeExecutionError(f"Container command timed out after {timeout}s")

    # ------------------------------------------------------------------ #
    #  3. Execute Python code inside a specific Docker container           #
    # ------------------------------------------------------------------ #
    def execute_python_in_container(
        self,
        container: str,
        code: str,
        timeout: int = EXEC_TIMEOUT,
    ) -> dict:
        """
        Write code to a temp file, copy it into the container, execute it.
        Safer than -c flag for multi-line code.
        """
        self._assert_syntax(code)

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            host_tmp = f.name

        container_tmp = f"/tmp/_agent_exec_{os.getpid()}.py"
        try:
            # Copy to container
            cp = subprocess.run(
                ["docker", "cp", host_tmp, f"{container}:{container_tmp}"],
                capture_output=True, text=True, timeout=10,
            )
            if cp.returncode != 0:
                raise CodeExecutionError(f"docker cp failed: {cp.stderr}")

            # Execute
            result = self.run_in_container(
                container, ["python3", container_tmp], timeout=timeout
            )

            # Cleanup inside container
            subprocess.run(
                ["docker", "exec", container, "rm", "-f", container_tmp],
                capture_output=True, timeout=5,
            )
            return result
        finally:
            try:
                os.unlink(host_tmp)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    #  4. Execute a loader function on a sample and validate output        #
    # ------------------------------------------------------------------ #
    def validate_loader_code(
        self,
        loader_code: str,
        sample_path: str,
        expected_keys: list,
        max_rows: int = 10,
    ) -> dict:
        """
        Validate a Claude-generated CSV loader function.
        Runs the function on up to max_rows rows of sample_path.
        Returns {ok, rows_checked, missing_keys, error}
        """
        wrapper = textwrap.dedent(f"""
import sys, json
from pathlib import Path

{loader_code}

path = Path({repr(sample_path)})
rows = list(load_csv(path))
sample = rows[:{max_rows}]
if not sample:
    print(json.dumps({{"ok": False, "error": "no rows returned"}}))
    sys.exit(0)

first = sample[0]
missing = [k for k in {repr(expected_keys)} if k not in first]
print(json.dumps({{"ok": len(missing)==0, "rows": len(sample), "missing_keys": missing, "first_keys": list(first.keys())}}))
""")
        res = self.execute_python(wrapper, timeout=20)
        if not res["ok"]:
            return {"ok": False, "error": res["stderr"]}
        try:
            return json.loads(res["stdout"].strip())
        except Exception:
            return {"ok": False, "error": f"bad output: {res['stdout'][:200]}"}

    # ------------------------------------------------------------------ #
    #  5. Validate and run pandas feature code on a DataFrame sample       #
    # ------------------------------------------------------------------ #
    def validate_feature_code(
        self,
        feature_lines: list,   # list of "df['x'] = ..." strings
        sample_parquet: str,
        max_rows: int = 20,
    ) -> dict:
        """
        Validate Claude-generated feature engineering lines.
        Returns {ok, new_columns, error}
        """
        lines_joined = "\n    ".join(feature_lines)
        wrapper = textwrap.dedent(f"""
import sys, json, shutil, tempfile
import pandas as pd
import pyarrow.parquet as pq

with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as tmp:
    tmp_path = tmp.name
shutil.copy2({repr(sample_parquet)}, tmp_path)
df = pq.read_table(tmp_path, use_threads=False).to_pandas().head({max_rows})
original_cols = set(df.columns)

try:
    {lines_joined}
    new_cols = [c for c in df.columns if c not in original_cols]
    print(json.dumps({{"ok": True, "new_columns": new_cols}}))
except Exception as e:
    print(json.dumps({{"ok": False, "error": str(e)}}))
""")
        res = self.execute_python(wrapper, timeout=30)
        if not res["ok"]:
            return {"ok": False, "error": res["stderr"]}
        try:
            return json.loads(res["stdout"].strip())
        except Exception:
            return {"ok": False, "error": f"bad output: {res['stdout'][:200]}"}

    # ------------------------------------------------------------------ #
    #  helpers                                                             #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _assert_syntax(code: str):
        try:
            compile(code, "<agent-generated>", "exec")
        except SyntaxError as e:
            raise CodeExecutionError(f"Syntax error in generated code: {e}") from e
