"""
Execute matplotlib code and return the resulting figure as base64 PNG.
Ported from gyaan_buddy_backend/gyaan_buddy/utils/matplotlib_executor.py.

Runs user-supplied code in a subprocess with a timeout for safety.
Automatically strips answer-revealing text from the figure before encoding.
"""
import base64
import logging
import re
import subprocess
import sys

logger = logging.getLogger("ai_service.matplotlib_executor")

EXECUTION_TIMEOUT = 30

_ANSWER_REVEAL_PATTERNS = [
    re.compile(r'^\s*(plt\.title|ax\d*\.set_title)\s*\(.*\)\s*$', re.MULTILINE),
    re.compile(r'^\s*plt\.suptitle\s*\(.*\)\s*$', re.MULTILINE),
    re.compile(r'^\s*(plt\.text|ax\d*\.text)\s*\(.*\)\s*$', re.MULTILINE),
    re.compile(r'^\s*ax\d*\.annotate\s*\(.*\)\s*$', re.MULTILINE),
    re.compile(r'^\s*plt\.figtext\s*\(.*\)\s*$', re.MULTILINE),
]


def sanitize_matplotlib_code(code: str) -> str:
    """
    Strip lines from matplotlib code that could render answer values inside the figure.
    Removes: plt.title, ax.set_title, plt.suptitle, plt.text, ax.text,
    ax.annotate, plt.figtext (single-line and multi-line calls).
    """
    if not code:
        return code

    cleaned = code
    for pattern in _ANSWER_REVEAL_PATTERNS:
        cleaned = pattern.sub('', cleaned)

    _MULTILINE_STARTS = (
        'plt.title(', 'ax.set_title(', 'plt.suptitle(',
        'plt.text(', 'ax.text(', '.annotate(', 'plt.figtext(',
    )
    lines = cleaned.splitlines()
    result_lines = []
    skip_depth = 0
    for line in lines:
        stripped = line.lstrip()
        if skip_depth > 0:
            skip_depth += line.count('(') - line.count(')')
            if skip_depth <= 0:
                skip_depth = 0
            continue
        if any(
            stripped.startswith(fn) or
            (f'.{fn.split(".")[-1]}' in stripped and stripped.startswith(fn.split('.')[0]))
            for fn in _MULTILINE_STARTS
        ):
            depth = line.count('(') - line.count(')')
            if depth > 0:
                skip_depth = depth
            continue
        result_lines.append(line)

    return '\n'.join(result_lines)


# Subprocess wrapper script — executed with the user code passed via stdin
_WRAPPER = r"""
import sys, base64, re as _re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

def _strip_answer_text(fig):
    _answer_re = _re.compile(r'[0-9\u00b0\u03b1-\u03c9\u0391-\u03a9]')
    for ax_obj in fig.get_axes():
        for txt in list(ax_obj.texts):
            content = txt.get_text().strip()
            if _answer_re.search(content) or len(content) > 2:
                txt.remove()
        ax_obj.set_title('')
        legend = ax_obj.get_legend()
        if legend:
            legend.remove()
        if _answer_re.search(ax_obj.get_xlabel()) or len(ax_obj.get_xlabel()) > 20:
            ax_obj.set_xlabel('')
        if _answer_re.search(ax_obj.get_ylabel()) or len(ax_obj.get_ylabel()) > 20:
            ax_obj.set_ylabel('')
        for label in ax_obj.get_xticklabels() + ax_obj.get_yticklabels():
            text = label.get_text().strip()
            if _answer_re.search(text) and len(text) > 3:
                label.set_text('')
    if fig._suptitle:
        fig.suptitle('')

code = sys.stdin.read()
try:
    exec(code, {'plt': plt, 'np': np, '__builtins__': __builtins__})
    _strip_answer_text(plt.gcf())
    buf = __import__('io').BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=150)
    plt.close('all')
    sys.stdout.buffer.write(base64.b64encode(buf.getvalue()))
except Exception as e:
    sys.stderr.write(str(e))
    sys.exit(1)
"""


def execute_matplotlib_code(matplotlib_code: str, timeout: int = EXECUTION_TIMEOUT) -> dict:
    """
    Execute matplotlib Python code in a subprocess and return the figure as base64 PNG.
    The code may use plt and np only.

    Returns:
        {"image_base64": str, "mime_type": "image/png"}  on success
        {"error": str}                                    on failure
    """
    if not matplotlib_code or not isinstance(matplotlib_code, str):
        return {"error": "matplotlib_code must be a non-empty string"}

    if len(matplotlib_code) > 50_000:
        return {"error": "matplotlib_code exceeds maximum allowed length"}

    try:
        proc = subprocess.run(
            [sys.executable, '-c', _WRAPPER],
            input=matplotlib_code.encode('utf-8'),
            capture_output=True,
            timeout=timeout,
        )
        if proc.returncode != 0:
            err = (proc.stderr or b'').decode('utf-8', errors='replace').strip() or 'Execution failed'
            logger.warning(f"Matplotlib execution failed: {err}")
            return {"error": f"Matplotlib execution failed: {err}"}
        if not proc.stdout:
            return {"error": "No image data produced"}
        return {"image_base64": proc.stdout.decode('ascii'), "mime_type": "image/png"}
    except subprocess.TimeoutExpired:
        logger.warning("Matplotlib execution timed out")
        return {"error": "Execution timed out"}
    except Exception as exc:
        logger.exception(f"Matplotlib executor error: {exc}")
        return {"error": str(exc)}
