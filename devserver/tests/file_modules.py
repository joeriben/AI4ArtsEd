"""Modules the suite loads from a file, and the two roots it loads them from.

load_module(name, path) executes a .py file as a module called `name`.
register=True puts the module into sys.modules before it runs, which is what
the package's own modules need to find one another: a node file that imports
ai4artsed_comfyui._card then finds the copy this test loaded, not an installed
package. Both forms stood in the test files themselves, copy for copy, until
the inventory of 2026-10-10 (finding S-109 of the code review of 2026-10-10).
"""
import importlib
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEVSERVER = Path(__file__).resolve().parents[1]


def load_module(name, path, *, register=False):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    if register:
        sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_index_builder():
    """scripts/build_knowledge_index.py, imported fresh each time."""
    scripts_dir = DEVSERVER / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    import build_knowledge_index as b
    return importlib.reload(b)
