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
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
            return cls._instances[cls]


class SingletonLazy:
    """
    Implements a thread-unsafe singleton pattern with lazy initialization.
    This singleton creates the instance only when it is first requested.
    """

    _instance = None

    @classmethod
    def getInstance(cls):
        """Return the singleton instance, creating it if it does not exist."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance


class SingletonEager:
    """
    Implements an eagerly initialized singleton.
    The instance of the singleton is created at the time of class loading.
    """

    _instance = None

    @classmethod
    def getInstance(cls):
        """Return the singleton instance."""
        return cls._instance


SingletonEager._instance = SingletonEager()  # Initializing the singleton instance


class SingletonDoubleChecked:
    """
    Implements a thread-safe singleton pattern with double-checked locking.
    This minimizes the performance overhead by only locking when the instance is being created.
    """

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def getInstance(cls):
        """Return the singleton instance, using double-checked locking for thread safety."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance
