import os
import sys

# Add project root to path
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

from Jarvis.core.orchestrator import Orchestrator

def main():
    print("Testing Orchestrator Error Auto-Recovery")
    orchestrator = Orchestrator()
    
    prompt = "Please run a PowerShell command to list the contents of a directory named C:\\ThisDirectoryDoesNotExist12345."
    print("User: " + prompt)
    
    result = orchestrator._process_with_llm(prompt)
    print("--- FINAL RESULT ---")
    print(result)

if __name__ == "__main__":
    main()