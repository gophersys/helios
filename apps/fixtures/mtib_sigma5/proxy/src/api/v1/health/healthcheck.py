import subprocess
import json
import logging
from flask import Blueprint, jsonify, make_response, request, has_request_context
import concurrent.futures

healthcheck_bp = Blueprint('healthcheck', __name__)

class SuppressHealthCheckLoggingFilter(logging.Filter):
     """
     The healthcheck route is hit pretty frequently by clusters and clients alike,
     therefore we want to omitt the logs of this route being hit by filtering the 
     default logs from the Flask library
     """
     def filter(self, record):
          if len(record.args) > 0 and record.args[0] == 'GET /v1/healthcheck HTTP/1.1':
               return False # Do not log if the path is the health check route
          return True

@healthcheck_bp.route('/v1/healthcheck', methods=['GET'])
def health_check():
     return "", 200
