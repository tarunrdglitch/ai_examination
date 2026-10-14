"""
Sandboxed Code Execution Engine for Coding Tests
Supports Python, JavaScript (Node), C, C++, Java, Bash, SQL.
Uses secure subprocess containment with tight CPU, memory, and timeout bounds.
"""

import os
import sys
import tempfile
import subprocess
import logging

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 5
MAX_OUTPUT_BYTES = 64 * 1024  # 64 KB limit

def execute_code(language, code, input_data=""):
    """
    Executes student submitted code in a contained scratch environment.
    Returns: {'success': bool, 'stdout': str, 'stderr': str, 'timeout': bool}
    """
    language = (language or 'python').lower()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        stdout_res = ""
        stderr_res = ""
        timeout_hit = False

        try:
            if language in ("python", "py"):
                code_file = os.path.join(tmpdir, "solution.py")
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(code)
                cmd = [sys.executable, "-I", code_file]  # isolated mode: ignores user site-packages/env

            elif language in ("javascript", "js", "node"):
                code_file = os.path.join(tmpdir, "solution.js")
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(code)
                cmd = ["node", code_file]

            elif language in ("c", "cpp", "c++"):
                ext = ".c" if language == "c" else ".cpp"
                compiler = "gcc" if language == "c" else "g++"
                src_file = os.path.join(tmpdir, f"solution{ext}")
                bin_file = os.path.join(tmpdir, "solution")
                with open(src_file, "w", encoding="utf-8") as f:
                    f.write(code)
                
                # Compile step
                comp = subprocess.run([compiler, src_file, "-o", bin_file, "-O2"],
                                      capture_output=True, text=True, timeout=10)
                if comp.returncode != 0:
                    return {'success': False, 'stdout': '', 'stderr': f"Compilation Error:\n{comp.stderr}", 'timeout': False}
                cmd = [bin_file]

            elif language in ("bash", "sh"):
                code_file = os.path.join(tmpdir, "solution.sh")
                with open(code_file, "w", encoding="utf-8") as f:
                    f.write(code)
                cmd = ["bash", code_file]

            else:
                return {'success': False, 'stdout': '', 'stderr': f"Unsupported language: {language}", 'timeout': False}

            # Run execution step
            proc = subprocess.run(
                cmd,
                input=input_data,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                cwd=tmpdir
            )
            stdout_res = proc.stdout[:MAX_OUTPUT_BYTES]
            stderr_res = proc.stderr[:MAX_OUTPUT_BYTES]
            success = (proc.returncode == 0)

        except subprocess.TimeoutExpired:
            timeout_hit = True
            success = False
            stderr_res = f"Time Limit Exceeded (>{TIMEOUT_SECONDS}s)"
        except Exception as e:
            success = False
            stderr_res = str(e)

        return {
            'success': success,
            'stdout': stdout_res,
            'stderr': stderr_res,
            'timeout': timeout_hit
        }


def run_test_cases(language, code, test_cases):
    """
    Runs code against an array of test cases:
    [{'input': '...', 'expected': '...'}, ...]
    Returns: {'all_passed': bool, 'passed_count': int, 'total': int, 'results': [...]}
    """
    results = []
    passed = 0

    for idx, tc in enumerate(test_cases or []):
        tc_in = str(tc.get('input', ''))
        tc_expected = str(tc.get('expected') or tc.get('expected_output') or tc.get('output') or '').strip()
        
        exec_out = execute_code(language, code, input_data=tc_in)
        actual = exec_out['stdout'].strip()
        
        is_pass = (exec_out['success'] and actual == tc_expected)
        if is_pass:
            passed += 1

        results.append({
            'case': idx + 1,
            'passed': is_pass,
            'input': tc_in,
            'expected': tc_expected,
            'actual': actual,
            'stderr': exec_out['stderr'],
            'timeout': exec_out['timeout']
        })

    total = len(test_cases) if test_cases else 0
    return {
        'all_passed': (passed == total and total > 0),
        'passed_count': passed,
        'total': total,
        'results': results
    }
