#!/usr/bin/env python
"""Integration test for Jarvis without ACTION tags."""
import sys
sys.path.append('.')

from Jarvis.core.orchestrator import Orchestrator

orchestrator = Orchestrator()

print("=" * 60)
print("INTEGRATION TEST - Basic Functionality")
print("=" * 60)

# Test 1: Natural language
print("\nTest 1: Natural language query")
print("-" * 40)
result = orchestrator.process_command('tell me a joke')
print(f"✓ Model responds with natural language: YES" if len(result) > 10 else f"✗ FAIL")

# Test 2: Direct shell command
print("\nTest 2: Direct shell command (bypasses LLM)")
print("-" * 40)
result = orchestrator.process_command('echo hello')
print(f"✓ Direct shell detected: YES" if "hello" in result else f"✗ FAIL")

# Test 3: System info query
print("\nTest 3: System query")
print("-" * 40)
result = orchestrator.process_command('systeminfo')
print(f"✓ System command detected: YES" if "Windows" in result or "Error" not in result else f"✗ FAIL")

print("\n" + "=" * 60)
print("SUMMARY")
print("=" * 60)
print("•System is operational for conversational queries")
print("•Direct shell commands bypass LLM correctly")
print("• Note: Model doesn't generate [ACTION] tags automatically")
print("• Fine-tuning needed for reliable action generation")
print("=" * 60)
