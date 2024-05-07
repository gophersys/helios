from flask import Blueprint

healthcheck_bp = Blueprint('healthcheck', __name__)
@healthcheck_bp.route('/v1/healthcheck', methods=['GET'])
def health_check():
     """
     This route just returns OK. Yes we're alive.
     """
     return "", 200
