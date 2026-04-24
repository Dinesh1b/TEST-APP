import sys, os
sys.path.insert(0, "/opt/render/project/src/vs code/vscode/main")
from backend.app import create_app
app = create_app()
