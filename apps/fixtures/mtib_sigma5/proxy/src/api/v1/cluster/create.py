# Standard includes
import logging
import os
import uuid
from typing import Tuple, Dict, Any

# 3rd party includes
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, Request, Response

# Server services
from src.services.proxy import proxy_server

# Route blue print
cluster_create_bp = Blueprint('cluster_create', __name__)

# ------------------------------------------------
#                                            Input
# ----------------------------------------------*/
class Input:
    def __init__(self, name: str, deployment_file: str):
        self.name = name
        self.deployment_file = deployment_file

    @staticmethod
    def from_request(req) -> Tuple[bool, str, "Input"]:
        name = req.form.get('name')
        if not name:
            return False, "Bad request, 'name' field is required.", None

        deployment_file = req.files.get('deployment_file')
        if not deployment_file:
            return False, "Bad request, 'deployment_file' field is required.", None

        # Generate a unique filename using only the secure filename portion
        unique_filename = f"{uuid.uuid4().hex}_{secure_filename(deployment_file.filename)}"

        # Ensure the /tmp directory exists (should not be necessary for /tmp but illustrative for deeper paths)
        temp_dir = '/tmp'
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(temp_dir, unique_filename)
        deployment_file.save(temp_file_path)

        return True, "", Input(name, temp_file_path)

# ------------------------------------------------
#                                           Output
# ----------------------------------------------*/
class Output:
    def __init__(self, uuid: str):
        self.uuid = uuid

    def to_json(self) -> Response:
        return jsonify({"uuid": self.uuid})

# ------------------------------------------------
#                                           Parse
# ----------------------------------------------*/
def parse(req: Request) -> Tuple[str, Input]:
    return Input.from_request(req)

# ------------------------------------------------
#                                         Validate
# ----------------------------------------------*/
def validate(input: Input) -> str:
    return True, ""

# ------------------------------------------------
#                                          Execute
# ----------------------------------------------*/
def execute(input: Input) -> Tuple[str, Output]:
    error, cluster_uuid = proxy_server.create_cluster(input.name, input.deployment_file)
    if error:
        return error, Output("")
    else:
        return "", Output(cluster_uuid)
        
# ------------------------------------------------
#                                          Respond
# ----------------------------------------------*/
def respond(error: str, output: Output) -> Response:
    if error:
        return jsonify({"error": error}), 400
    else:
        return output.to_json(), 200
       

# -------------------------------------------------------------------------------------------------
#                                                                                             Route
# -----------------------------------------------------------------------------------------------*/
@cluster_create_bp.route('/v1/cluster', methods=['POST'])
def register_cluster():
    """
    Registers a new cluster
    """
    try:
        success, error, input = parse(request)
        if not success:
            return jsonify({"error": f"Invalid request data: {error}"}), 400

        success, error = validate(input)
        if not success:
            return jsonify({"error": f"Invalid input: {error}"}), 400

        error, output = execute(input)
        return respond(error, output)

    except Exception as e:
        logging.error("An error occurred: %s", str(e))
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500