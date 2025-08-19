import logging
from flask import Flask
from flask_socketio import SocketIO

# V1 Routes
from .log_filter import LogFilter
from .healthcheck import healthcheck_bp
from .storage import storage_bp
from .auth.tokens.request import tokens_request_bp
from .auth.tokens.refresh import token_refresh_bp
from .devices.validate_snr import devices_snr_validate_bp
from .devices.assign_device_id import devices_assign_id_bp
from .devices.save_iccid import devices_save_iccid_bp
from .devices.upload_pub_key import devices_save_pub_key_bp
from .devices.alpha.get_algo_update import devices_alpha_algo_update_bp
from .clusters.create import clusters_create_bp
from .clusters.get_uuid import clusters_get_uuid_bp
from .clusters.list import clusters_list_bp
from .clusters.delete_all import clusters_delete_all_bp
from .clusters.delete_uuid import clusters_delete_uuid_bp
from .clusters.register_uuid import clusters_register_uuid_bp
from .clusters.deployments.create import clusters_deployments_create_bp
from .clusters.deployments.get_uuid import clusters_deployments_get_uuid_bp
from .clusters.deployments.list import clusters_deployments_list_bp
from .clusters.deployments.delete_uuid import clusters_deployments_delete_uuid_bp
from .clusters.deployments.delete_all import clusters_deployments_delete_all_bp
from .clusters.deployments.status_uuid import clusters_deployments_status_uuid_bp
from .clusters.deployments.apply_uuid import clusters_deployments_apply_uuid_bp
from .clusters.tests.get_uuid import clusters_tests_get_uuid_bp
from .clusters.tests.list import clusters_tests_list_bp
from .clusters.tests.exec_uuid import clusters_tests_exec_uuid_bp
from .clusters.tests.exec_uuid import clusters_tests_exec_uuid_socketio_handler
from .clusters.tests.stop_uuid import clusters_tests_stop_uuid_bp
from .clusters.executions.get_uuid import clusters_executions_get_uuid_bp
from .clusters.executions.list import clusters_executions_list_bp
from .clusters.executions.delete_uuid import clusters_executions_delete_uuid_bp
from .clusters.executions.delete_all import clusters_executions_delete_all_bp
from .obsv.memory.start import obsv_memory_start_bp
from .obsv.memory.record import obsv_memory_record_bp


def register_v1_routes(server: Flask, socketio: SocketIO):
    # Add a log filter to avoid spamming the logs with commonly hit routes
    logging.getLogger().addFilter(LogFilter())

    server.register_blueprint(healthcheck_bp)  # GET /v1/healthcheck
    server.register_blueprint(storage_bp)  # GET /v1/storage

    # Auth
    server.register_blueprint(tokens_request_bp)  # POST /v1/auth/tokens/request
    server.register_blueprint(token_refresh_bp)  # POST /v1/auth/tokens/refresh

    # Devices
    server.register_blueprint(devices_snr_validate_bp)  # POST /v1/devices/snr/validate
    server.register_blueprint(devices_assign_id_bp)  # POST /v1/devices/ids/assign
    server.register_blueprint(devices_save_iccid_bp)  # POST /v1/devices/iccids/save
    server.register_blueprint(devices_save_pub_key_bp)  # POST /v1/devices/keys/upload
    server.register_blueprint(devices_alpha_algo_update_bp)  # POST /v1/devices/alpha/algo/update

    # Clusters
    server.register_blueprint(clusters_create_bp)  # POST /v1/clusters
    server.register_blueprint(clusters_get_uuid_bp)  # GET /v1/clusters/<uuid>
    server.register_blueprint(clusters_list_bp)  # GET /v1/clusters
    server.register_blueprint(clusters_delete_all_bp)  # DELETE /v1/clusters
    server.register_blueprint(clusters_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>
    server.register_blueprint(clusters_register_uuid_bp)  # POST /v1/clusters/<uuid>/register

    # Cluster Deployments
    server.register_blueprint(clusters_deployments_create_bp)  # POST /v1/clusters/<uuid>/deployments
    server.register_blueprint(clusters_deployments_get_uuid_bp)  # GET /v1/clusters/<uuid>/deployments/<uuid>
    server.register_blueprint(clusters_deployments_status_uuid_bp)  # GET /v1/clusters/<uuid>/deployments/<uuid>/status
    server.register_blueprint(clusters_deployments_list_bp)  # GET /v1/clusters/<uuid>/deployments
    server.register_blueprint(clusters_deployments_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>/deployments/<uuid>
    server.register_blueprint(clusters_deployments_delete_all_bp)  # DELETE /v1/clusters/<uuid>/deployments
    server.register_blueprint(clusters_deployments_apply_uuid_bp)  # POST /v1/clusters/<uuid>/deployments/<uuid>/apply

    # Cluster Tests
    server.register_blueprint(clusters_tests_get_uuid_bp)  # GET /v1/clusters/<uuid>/tests/<uuid>
    server.register_blueprint(clusters_tests_list_bp)  # GET /v1/clusters/<uuid>/tests
    server.register_blueprint(clusters_tests_exec_uuid_bp)  # POST /v1/clusters/<uuid>/tests/<uuid>/exec
    server.register_blueprint(clusters_tests_stop_uuid_bp)  # POST /v1/clusters/<uuid>/tests/<uuid>/stop

    @socketio.on("exec_test")
    def handle_ws_event_exec_test(data):
        clusters_tests_exec_uuid_socketio_handler(data, socketio)

    # Cluster Executions
    server.register_blueprint(clusters_executions_get_uuid_bp)  # GET /v1/clusters/<uuid>/executions/<uuid>
    server.register_blueprint(clusters_executions_list_bp)  # GET /v1/clusters/<uuid>/executions
    server.register_blueprint(clusters_executions_delete_uuid_bp)  # DELETE /v1/clusters/<uuid>/executions/<uuid>
    server.register_blueprint(clusters_executions_delete_all_bp)  # DELETE /v1/clusters/<uuid>/executions

    # Observability
    server.register_blueprint(obsv_memory_start_bp)  # POST /v1/obsv/memory/start
    server.register_blueprint(obsv_memory_record_bp)  # POST /v1/obsv/memory/<session_id>/record
