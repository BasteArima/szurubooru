from typing import Dict

from szurubooru import rest
from szurubooru.func import (
    auth,
    auto_tag,
    auto_tag_config,
    auto_tag_jobs,
    posts,
)


@rest.routes.get("/auto-tag/config/?")
def get_config(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    return {"config": auto_tag_config.get_public_config()}


@rest.routes.put("/auto-tag/config/?")
def set_config(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    incoming = ctx._params.get("config") or {}
    result = auto_tag_config.update_config(incoming)
    ctx.session.commit()
    return {"config": result}


@rest.routes.get("/auto-tag/job/?")
def get_job(ctx: rest.Context, _params: Dict[str, str] = {}) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    return {"job": auto_tag_jobs.serialize_job(auto_tag_jobs.get_current_job())}


@rest.routes.post("/auto-tag/job/?")
def start_job(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    methods = ctx.get_param_as_string_list("methods", default=[])
    mode = ctx.get_param_as_string("mode", default="new")
    retry_empty = ctx.get_param_as_bool("retryEmpty", default=False)
    query = ctx.get_param_as_string("query", default="")
    return {"job": auto_tag_jobs.start_job(methods, mode, retry_empty, query)}


@rest.routes.post("/auto-tag/job/pause/?")
def pause_job(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    return {"job": auto_tag_jobs.pause_job()}


@rest.routes.post("/auto-tag/job/resume/?")
def resume_job(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    return {"job": auto_tag_jobs.resume_job()}


@rest.routes.post("/auto-tag/job/cancel/?")
def cancel_job(
    ctx: rest.Context, _params: Dict[str, str] = {}
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    return {"job": auto_tag_jobs.cancel_job()}


@rest.routes.get("/post/(?P<post_id>[^/]+)/auto-tag/?")
def get_post_auto_tag_state(
    ctx: rest.Context, params: Dict[str, str]
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    post = posts.get_post_by_id(int(params["post_id"]))
    return {"autoTagState": auto_tag.serialize_post_state(post.post_id)}


@rest.routes.post("/post/(?P<post_id>[^/]+)/auto-tag/?")
def auto_tag_post(
    ctx: rest.Context, params: Dict[str, str]
) -> rest.Response:
    auth.verify_privilege(ctx.user, "posts:auto_tag")
    post = posts.get_post_by_id(int(params["post_id"]))
    methods = ctx.get_param_as_string_list(
        "methods", default=list(auto_tag.METHODS)
    )
    methods = [m for m in methods if m in auto_tag.METHODS]
    cfg = auto_tag_config.get_config()
    results = auto_tag.run_methods_on_post(post, methods, cfg)
    return {
        "results": results,
        "autoTagState": auto_tag.serialize_post_state(post.post_id),
    }
