import sys
import os

# Ensure libs/python and libs/protocols are on the path
libs_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".."))
sys.path.insert(0, os.path.join(libs_root))
sys.path.insert(0, os.path.join(libs_root, "..", "protocols"))
sys.path.insert(0, os.path.join(libs_root, ".."))
