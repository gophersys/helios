from flask import Blueprint, request
import logging

# Application server
from src.proxy import ProxyServer, TestCluster, ClusterStatus, TestInfo

# Assuming 'logging' has been configured at the application level
test_execute_bp = Blueprint('test_execute', __name__)

@test_execute_bp.route('/v1/cluster/<cluster_id>/tests/<test_id>/execute', methods=['POST'])
def test_execute(cluster_id, test_id):
    ProxyServer().exec_cluster_test(cluster_id, test_id, [0,2,4,5])
    return "", 200
