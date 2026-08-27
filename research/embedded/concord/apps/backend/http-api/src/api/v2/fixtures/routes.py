"""Route registration for /v2/fixtures and /v2/dashboard endpoints."""

from flask import Blueprint

from .fixtures import (
    batch_fixtures_action,
    dashboard_overview,
    list_fixtures,
    create_fixture as create_managed_fixture,
    get_fixture,
    update_fixture,
    delete_fixture,
    create_slot,
    update_slot,
    delete_slot,
    assign_slot_node,
    deploy_fixture,
    undeploy_fixture,
    get_fixture_deploy_status,
)
from .benches import (
    list_benches, get_bench, create_bench, update_bench, delete_bench,
    discover_mtibs, get_bench_profile,
)
from .designs import (
    list_designs, get_design, create_design, update_design,
    delete_design, get_design_profile,
)


def register_fixture_routes(api: Blueprint):
    api.add_url_rule("/fixtures",                                         endpoint="list_fixtures",           view_func=list_fixtures,            methods=["GET"])
    api.add_url_rule("/fixtures",                                         endpoint="create_fixture",          view_func=create_managed_fixture,   methods=["POST"])
    api.add_url_rule("/fixtures/<fixture_id>",                            endpoint="get_fixture",             view_func=get_fixture,              methods=["GET"])
    api.add_url_rule("/fixtures/<fixture_id>",                            endpoint="update_fixture",          view_func=update_fixture,           methods=["PUT"])
    api.add_url_rule("/fixtures/<fixture_id>",                            endpoint="delete_fixture",          view_func=delete_fixture,           methods=["DELETE"])
    api.add_url_rule("/fixtures/<fixture_id>/slots",                      endpoint="create_slot",             view_func=create_slot,              methods=["POST"])
    api.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="update_slot",             view_func=update_slot,              methods=["PUT"])
    api.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>",            endpoint="delete_slot",             view_func=delete_slot,              methods=["DELETE"])
    api.add_url_rule("/fixtures/<fixture_id>/slots/<slot_id>/assign",     endpoint="assign_slot_node",        view_func=assign_slot_node,         methods=["POST"])
    api.add_url_rule("/fixtures/<fixture_id>/deploy",                    endpoint="deploy_fixture",          view_func=deploy_fixture,           methods=["POST"])
    api.add_url_rule("/fixtures/<fixture_id>/undeploy",                  endpoint="undeploy_fixture",        view_func=undeploy_fixture,         methods=["POST"])
    api.add_url_rule("/fixtures/<fixture_id>/deploy-status",            endpoint="fixture_deploy_status",   view_func=get_fixture_deploy_status, methods=["GET"])
    api.add_url_rule("/fixtures/batch",                                  endpoint="batch_fixtures",          view_func=batch_fixtures_action,     methods=["POST"])

    api.add_url_rule("/fixtures/benches",                                endpoint="list_benches",                 view_func=list_benches,             methods=["GET"])
    api.add_url_rule("/fixtures/benches",                                endpoint="create_bench",                 view_func=create_bench,             methods=["POST"])
    api.add_url_rule("/fixtures/benches/discover",                       endpoint="discover_mtibs",               view_func=discover_mtibs,           methods=["GET"])
    api.add_url_rule("/fixtures/benches/<bench_id>",                     endpoint="get_bench",                    view_func=get_bench,                methods=["GET"])
    api.add_url_rule("/fixtures/benches/<bench_id>",                     endpoint="update_bench",                 view_func=update_bench,             methods=["PATCH"])
    api.add_url_rule("/fixtures/benches/<bench_id>",                     endpoint="delete_bench",                 view_func=delete_bench,             methods=["DELETE"])
    api.add_url_rule("/fixtures/benches/<bench_id>/profile",             endpoint="get_bench_profile",            view_func=get_bench_profile,        methods=["GET"])

    api.add_url_rule("/test-bed-designs",                                endpoint="list_designs",                 view_func=list_designs,             methods=["GET"])
    api.add_url_rule("/test-bed-designs",                                endpoint="create_design",                view_func=create_design,            methods=["POST"])
    api.add_url_rule("/test-bed-designs/<design_id>",                    endpoint="get_design",                   view_func=get_design,               methods=["GET"])
    api.add_url_rule("/test-bed-designs/<design_id>",                    endpoint="update_design",                view_func=update_design,            methods=["PATCH"])
    api.add_url_rule("/test-bed-designs/<design_id>",                    endpoint="delete_design",                view_func=delete_design,            methods=["DELETE"])
    api.add_url_rule("/test-bed-designs/<design_id>/profile",            endpoint="get_design_profile",           view_func=get_design_profile,       methods=["GET"])

    api.add_url_rule("/dashboard/overview",                              endpoint="dashboard_overview",          view_func=dashboard_overview,         methods=["GET"])
