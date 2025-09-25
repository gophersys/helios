import threading


class SingletonThreadSafeMeta(type):
    """
    A thread-safe implementation of a Singleton pattern using a metaclass.
    This ensures that only one instance of each class is created, even in a multi-threaded environment.
    """

    _instances = {}
    _lock = threading.Lock()

    def __call__(cls, *args, **kwargs):
        """Returns a single instance of the class."""

        # Handle namespaces for database environments
        db_env = kwargs.get("db_env", "VAL_1_0")
        key = (cls, db_env)

        with cls._lock:
            if key not in cls._instances:
                cls._instances[key] = super().__call__(*args, **kwargs)
            return cls._instances[key]
