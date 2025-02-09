import sys
from pathlib import Path

def setup_path():
    """Add the project root directory to Python path"""
    # Get the project root directory
    project_root = Path(__file__).parent.parent.parent
    src_path = project_root / 'src'
    
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    if str(src_path) not in sys.path:
        sys.path.append(str(src_path))
