
import os
dirs = ["Jarvis", "Jarvis/core", "Jarvis/input", "Jarvis/output", "Jarvis/ui"]
for d in dirs:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), d, "__init__.py")
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write("# Package initialization")
        print(f"Cleaned {path}")
    except Exception as e:
        print(f"Error cleaning {path}: {e}")
