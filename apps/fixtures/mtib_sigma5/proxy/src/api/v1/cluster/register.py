# Standard includes
import logging
from typing import Tuple, Dict, Any

# 3rd party includes
from flask import Blueprint, jsonify, request, Request, Response

# Server services
from src.services.proxy import ProxyServer

# Route blue print
sample_bp = Blueprint('sample', __name__)

# ------------------------------------------------
#                                            Input
# ----------------------------------------------*/
class Input:
    def __init__(self, url: str):
        self.url = url

    @staticmethod
    def from_request(req) -> Tuple[bool, str, "Input"]:
        data = req.get_json(silent=True) or {}
        url = data.get('url')
        if not url or not isinstance(url, str):
            return False, "Bad request, 'url' field is required and must be a string.", None
        return True, "", Input(url)

# ------------------------------------------------
#                                           Output
# ----------------------------------------------*/
class Output:
    def __init__(self):
        pass

    def to_json(self) -> Response:
        return jsonify({})

# ------------------------------------------------
#                                           Parse
# ----------------------------------------------*/
def parse(req:Request) -> Tuple[bool, str, Input]:
    """
    Parses the request data and returns a tuple indicating success/failure, an error message if any, 
    and the parsed input data.
    
    :param req: The Flask request object.
    :return: Tuple indicating success (True/False), error message (str), and the parsed input (Input object).
    """
    return Input.from_request(req)

# ------------------------------------------------
#                                         Validate
# ----------------------------------------------*/
def validate(input: Input) -> Tuple[bool, str]:
    """
    Validates the parsed input data.
    
    :param input: Parsed input data encapsulated in an Input object.
    :return: Tuple indicating success (True/False) and error message (str) if any.
    """
    if not input.url:
        return False, "URL cannot be empty."
    return True, ""

# ------------------------------------------------
#                                          Execute
# ----------------------------------------------*/
def execute(input: Input) -> Tuple[int, Output]:
    """
    Executes the business logic with the provided input data and produces an output.

    :param input: Parsed input data encapsulated in an Input object.
    :return: Tuple indicating status code, and the output struct to be sent back as a response.
    """
    proxy_server = ProxyServer()
    success = proxy_server.register_cluster(input.url)
    if success:
        return True, 200, Output()
    else:
        return False, 503, Output()

# ------------------------------------------------
#                                          Respond
# ----------------------------------------------*/
def respond(status_code: int, output:Output) -> Response:
    """
    Puts together a response based on the business logic exection.
    """
    if status_code == 200:
        return output.to_json(), status_code
    elif status_code == 503:
        return jsonify({"error": "Service Unavailable: Unable to register the cluster."}), status_code
    else:
        return jsonify({"error": "Internal Server Error"}), 500

# ------------------------------------------------
#                                          Action
# ----------------------------------------------*/
def action(output: Output):
    """
    No action for this server
    """
    pass

# -------------------------------------------------------------------------------------------------
#                                                                                             Route
# -----------------------------------------------------------------------------------------------*/
@sample_bp.route('/v1/sample', methods=['GET'])
def healthcheck():
    """
    Orchestrates the parsing, validation, execution of business logic, and the response creation.
    
    :return: A Flask JSON response
    """
    try:
        success, error, input = parse(request)
        if not success:
            return jsonify({"error": f"Invalid request data: {error}"}), 400

        success, error = validate(input)
        if not success:
            return jsonify({"error": f"Invalid input: {error}"}), 400

        status_code, output = execute(input)
        return respond(status_code, output)
    
    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return jsonify({"error": f"Internal server error"}), 500