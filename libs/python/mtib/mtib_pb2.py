"""Re-export from protocols.mtib.mtib_pb2."""
from protocols.mtib.mtib_pb2 import *  # noqa
from protocols.mtib import mtib_pb2
# Make this module look like the original
import sys
sys.modules[__name__] = mtib_pb2
