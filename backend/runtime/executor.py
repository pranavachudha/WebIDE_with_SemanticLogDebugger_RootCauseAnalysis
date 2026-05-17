import subprocess
import tempfile
import os
import sys
import time
from parser.traceback_parser import extract_code_context, parse_traceback

CURRENT_PROCESS = None

def execute_code(code: str, filename: str = 'main.py'):
    """Executes python code in a subprocess and captures output and traceback."""
    suffix = os.path.splitext(filename)[1] or '.py'
    with tempfile.NamedTemporaryFile(mode='w', suffix=suffix, delete=False, encoding='utf-8') as f:
        f.write(code)
        temp_file = f.name

    global CURRENT_PROCESS
    start_time = time.time()
    try:
        process = subprocess.Popen(
            [sys.executable, temp_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        CURRENT_PROCESS = process
        stdout, stderr = process.communicate(timeout=10)
        return_code = process.returncode

        elapsed = time.time() - start_time
        output = stdout
        error_output = stderr

        if return_code != 0:
            parsed_error = parse_traceback(error_output)
            context = extract_code_context(code, parsed_error.get('line_number', -1), radius=10)
            return {
                'output': output,
                'execution_time': f"{elapsed:.2f}s",
                'error': {
                    'type': parsed_error.get('exception_type', 'UnknownError'),
                    'message': parsed_error.get('message', error_output),
                    'traceback': error_output,
                    'line_number': parsed_error.get('line_number', -1),
                    'file_name': parsed_error.get('file', temp_file),
                    'failing_function': context.get('failing_function') or parsed_error.get('failing_function', ''),
                    'call_stack': parsed_error.get('call_stack', []),
                    'code_context': context,
                }
            }

        return {
            'success': True,
            'stdout': output,
            'stderr': '',
            'traceback': '',
            'execution_time': f"{elapsed:.2f}s",
            'error': None,
        }
    except subprocess.TimeoutExpired:
        if CURRENT_PROCESS is not None:
            CURRENT_PROCESS.kill()
            CURRENT_PROCESS = None
        return {
            'success': False,
            'stdout': '',
            'stderr': 'Code execution exceeded the 10 second timeout.',
            'traceback': 'TimeoutError: Code execution exceeded the 10 second timeout.',
            'execution_time': '10.00s',
            'error': {
                'type': 'TimeoutError',
                'message': 'Code execution exceeded the 10 second timeout.',
                'traceback': 'TimeoutError: Code execution exceeded the 10 second timeout.',
                'line_number': -1,
            }
        }
    except Exception as e:
        return {
            'success': False,
            'stdout': '',
            'stderr': str(e),
            'traceback': str(e),
            'execution_time': f"{time.time() - start_time:.2f}s",
            'error': {
                'type': type(e).__name__,
                'message': str(e),
                'traceback': str(e),
                'line_number': -1,
            }
        }
    finally:
        CURRENT_PROCESS = None
        if os.path.exists(temp_file):
            os.remove(temp_file)


def stop_execution():
    global CURRENT_PROCESS
    if CURRENT_PROCESS is not None and CURRENT_PROCESS.poll() is None:
        try:
            CURRENT_PROCESS.kill()
            return True
        except Exception:
            return False
    return False
