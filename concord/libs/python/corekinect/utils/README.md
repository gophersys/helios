# Corekinect Python Utilities Library

## Modules

- **Env**: Environment configuration management.
- **Log**: Custom logging utilities.
- **Bit Manipulation**: Functions for manipulating bits.
- **Encoding**: Encoding and decoding utilities.
- **Math Utils**: Mathematical functions like the Haversine formula.
- **Temperature**: Temperature conversion functions.
- **Progress**: Progress bar utilities.
- **Datetime Utils**: Datetime conversion functions.
- **Version Checker**: Check that a given firmware version is supported by a test or test step
- **Singleton**: Classes for implementing the singleton patterns.


## Example Usage


### Bit Manipulation

```python
from utils import get_bits, set_bits

bit_mask = 0
bit_mask = set_bits(bit_mask, 0, 3, 5)
bit_mask = set_bits(bit_mask, 4, 7, 10)

bit_range_0_3 = get_bits(bit_mask, 0, 3)
bit_range_4_7 = get_bits(bit_mask, 4, 7)


```

## Math Utils
```python
from corekinect.utils import haversine

distance = haversine(36.12, -86.67, 33.94, -118.40, in_miles=True)
```

### Logger
```python
from corekinect.utils import Logger

# Basic Logging
log = Logger()
log.info("Something worth logging")


# For logging in test steps and test helpers
test_log = Logger.get_test_case_logger()
test_log.info("This will be logged in within the test case context")

```

## Version Checker

```python
from corekinect.version_support import is_version_supported

# Define the full version to check
full_version = "1.2.3"

# Define supported versions (can be a string or a list of strings)
supported_versions = ["1.x", "2.0"]

# Check if the version is supported
if is_version_supported(full_version, supported_versions):
    print(f"Version {full_version} is supported.")
else:
    print(f"Version {full_version} is not supported.")

```

## Singleton

``python
from corekinect.utils import SingletonThreadedMeta

class MySingleton(metaclass=SingletonThreadedMeta):
    """
    Example singleton class using SingletonThreadedMeta for thread-safe instantiation.
    """
    def __init__(self):
        self.name = "MySingletonInstance"

    def show(self):
        print(f"Instance ID: {id(self)} - Name: {self.name}")

# Creating singleton instances in a multi-threaded environment
if __name__ == "__main__":
    import threading

    def create_singleton():
        instance = MySingleton()
        instance.show()

    # Create multiple threads to test singleton behavior
    for _ in range(5):
        threading.Thread(target=create_singleton).start()
```