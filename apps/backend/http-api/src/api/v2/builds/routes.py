"""Route registration for /v2/builds endpoints."""

from flask import Blueprint
from flask_socketio import SocketIO

from .webhook import webhook_bitbucket, trigger_build_run, receive_repo_event, set_ci_socketio, list_ci_repos
from .builds import (
    list_builds as list_ci_builds,
    get_build as get_ci_build,
    list_build_artifacts as list_ci_build_artifacts,
    download_build_artifacts as download_ci_build_artifacts,
    download_single_artifact as download_ci_single_artifact,
    get_build_log as get_ci_build_log,
    stream_build_log as stream_ci_build_log,
    report_build_progress as report_ci_build_progress,
    create_build as create_ci_build,
    update_build as update_ci_build,
    upload_build_artifact as upload_ci_build_artifact,
    reset_build as reset_ci_build,
)
from .queue_priority import set_build_priority, promote_build, demote_build
from .build_runs import (
    batch_build_runs_action,
    list_build_runs as list_ci_build_runs,
    get_build_run as get_ci_build_run,
    create_build_run as create_ci_build_run,
    cancel_build_run as cancel_ci_build_run,
    retrigger_build_run as retrigger_ci_build_run,
    download_build_run_artifacts as download_ci_build_run_artifacts,
    validate_build_run as validate_ci_build_run,
    validate_build_run_artifacts_endpoint as validate_ci_build_run_artifacts,
    list_build_run_sessions as list_ci_build_run_sessions,
)
from .scripts import list_build_scripts, get_build_script
from .overlays import get_overlays, list_overlays
from .pr_builds import list_pr_build_runs, get_build_summary
from .recipes import get_stage_defs, list_recipe_templates, get_recipe_template


def register_build_routes(api: Blueprint, socketio: SocketIO):
    # Webhooks & Triggers
    api.add_url_rule("/builds/webhooks/bitbucket",                                               endpoint="ci_webhook_bitbucket",     view_func=webhook_bitbucket,     methods=["POST"])
    api.add_url_rule("/builds/trigger",                                                          endpoint="ci_trigger_build_run",      view_func=trigger_build_run,      methods=["POST"])
    api.add_url_rule("/builds/events",                                                           endpoint="ci_receive_repo_event",     view_func=receive_repo_event,     methods=["POST"])

    # Builds CRUD
    api.add_url_rule("/builds",                                                                  endpoint="list_ci_builds",           view_func=list_ci_builds,        methods=["GET"])
    api.add_url_rule("/builds",                                                                  endpoint="create_ci_build",          view_func=create_ci_build,       methods=["POST"])
    api.add_url_rule("/builds/<build_id>",                                                       endpoint="get_ci_build",             view_func=get_ci_build,          methods=["GET"])
    api.add_url_rule("/builds/<build_id>",                                                       endpoint="update_ci_build",          view_func=update_ci_build,       methods=["PATCH"])
    api.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="list_ci_build_artifacts",  view_func=list_ci_build_artifacts, methods=["GET"])
    api.add_url_rule("/builds/<build_id>/artifacts",                                             endpoint="upload_ci_build_artifact", view_func=upload_ci_build_artifact, methods=["POST"])
    api.add_url_rule("/builds/<build_id>/artifacts/download",                                    endpoint="download_ci_build_artifacts", view_func=download_ci_build_artifacts, methods=["GET"])
    api.add_url_rule("/builds/<build_id>/artifacts/<artifact_name>",                             endpoint="download_ci_single_artifact", view_func=download_ci_single_artifact, methods=["GET"])
    api.add_url_rule("/builds/<build_id>/log",                                                   endpoint="get_ci_build_log",         view_func=get_ci_build_log,      methods=["GET"])
    api.add_url_rule("/builds/<build_id>/log",                                                   endpoint="stream_ci_build_log",      view_func=stream_ci_build_log,   methods=["POST"])
    api.add_url_rule("/builds/<build_id>/progress",                                              endpoint="report_ci_build_progress", view_func=report_ci_build_progress, methods=["POST"])
    api.add_url_rule("/builds/<build_id>/reset",                                                 endpoint="reset_ci_build",           view_func=reset_ci_build,        methods=["POST"])
    api.add_url_rule("/builds/<build_id>/priority",                                               endpoint="set_build_priority",       view_func=set_build_priority,    methods=["PATCH"])
    api.add_url_rule("/builds/<build_id>/promote",                                                endpoint="promote_build",            view_func=promote_build,         methods=["POST"])
    api.add_url_rule("/builds/<build_id>/demote",                                                 endpoint="demote_build",             view_func=demote_build,          methods=["POST"])

    # PR Builds & Summary
    api.add_url_rule("/builds/prs",                                                         endpoint="list_pr_build_runs",       view_func=list_pr_build_runs,     methods=["GET"])
    api.add_url_rule("/builds/summary",                                                     endpoint="get_build_summary",        view_func=get_build_summary,      methods=["GET"])

    # Build Runs
    api.add_url_rule("/builds/runs",                                                        endpoint="list_build_runs",          view_func=list_ci_build_runs,     methods=["GET"])
    api.add_url_rule("/builds/runs",                                                        endpoint="create_build_run",         view_func=create_ci_build_run,    methods=["POST"])
    api.add_url_rule("/builds/runs/<run_id>",                                          endpoint="get_build_run",            view_func=get_ci_build_run,       methods=["GET"])
    api.add_url_rule("/builds/runs/<run_id>/cancel",                                   endpoint="cancel_build_run",         view_func=cancel_ci_build_run,    methods=["POST"])
    api.add_url_rule("/builds/runs/<run_id>/retrigger",                               endpoint="retrigger_build_run",      view_func=retrigger_ci_build_run, methods=["POST"])
    api.add_url_rule("/builds/runs/<run_id>/validate",                                endpoint="validate_build_run",       view_func=validate_ci_build_run,  methods=["POST"])
    api.add_url_rule("/builds/runs/<run_id>/artifacts/download",                       endpoint="download_build_run_artifacts", view_func=download_ci_build_run_artifacts, methods=["GET"])
    api.add_url_rule("/builds/runs/<run_id>/sessions",                               endpoint="list_build_run_sessions",  view_func=list_ci_build_run_sessions, methods=["GET"])
    api.add_url_rule("/builds/runs/<run_id>/validate-artifacts",                     endpoint="validate_build_run_artifacts", view_func=validate_ci_build_run_artifacts, methods=["POST"])
    api.add_url_rule("/builds/runs/batch",                                            endpoint="batch_build_runs",             view_func=batch_build_runs_action,         methods=["POST"])

    # Settings
    api.add_url_rule("/builds/settings/repos",                                                   endpoint="list_ci_repos",            view_func=list_ci_repos,         methods=["GET"])

    # Scripts
    api.add_url_rule("/builds/scripts",                                                          endpoint="list_build_scripts",       view_func=list_build_scripts,    methods=["GET"])
    api.add_url_rule("/builds/scripts/<product>",                                                endpoint="get_build_script",         view_func=get_build_script,      methods=["GET"])

    # Overlays
    api.add_url_rule("/builds/overlays/<product>",                                               endpoint="get_overlays",             view_func=get_overlays,          methods=["GET"])
    api.add_url_rule("/builds/overlays/<product>/list",                                          endpoint="list_overlays",            view_func=list_overlays,         methods=["GET"])

    # Stage Definitions
    api.add_url_rule("/builds/stage-defs",                                                       endpoint="get_stage_defs",           view_func=get_stage_defs,        methods=["GET"])

    # Recipe Templates
    api.add_url_rule("/builds/recipe-templates",                                                 endpoint="list_recipe_templates",    view_func=list_recipe_templates, methods=["GET"])
    api.add_url_rule("/builds/recipe-templates/<template_id>",                                   endpoint="get_recipe_template",      view_func=get_recipe_template,   methods=["GET"])

    set_ci_socketio(socketio)
