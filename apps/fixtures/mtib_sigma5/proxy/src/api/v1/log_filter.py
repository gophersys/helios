import logging
import re

class LogFilter(logging.Filter):
    """
    This filter omits the logs for frequently accessed routes such as healthcheck and deployment routes.
    The deployment route includes a UUID, so we use regular expressions to match both patterns.
    """
    def __init__(self):
        # Compile regular expressions only once for efficiency
        self.healthcheck_route_pattern = re.compile(r'GET /v1/healthcheck HTTP/1\.1')
        self.deployment_route_pattern = re.compile(r'GET /v1/clusters/[0-9a-fA-F\-]{36}/deployments HTTP/1\.1')

    def filter(self, record):
        # Check if the log record matches any of the specified route patterns
        if len(record.args) > 0:
            log_message = record.args[0]
            if (self.healthcheck_route_pattern.match(log_message) or
                self.deployment_route_pattern.match(log_message)):
                return False  # Do not log if the path matches any of the patterns
        return True
