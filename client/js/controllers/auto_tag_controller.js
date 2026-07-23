"use strict";

const api = require("../api.js");
const uri = require("../util/uri.js");
const topNavigation = require("../models/top_navigation.js");
const AutoTagView = require("../views/auto_tag_view.js");
const EmptyView = require("../views/empty_view.js");

const ACTIVE = ["running", "paused", "cancelling"];

// Full config skeleton the template relies on. The server normalizes to this
// shape too, but keeping a client-side default makes the page resilient to a
// server that's a version behind (secrets arrive as booleans, hence false).
const CONFIG_DEFAULTS = {
    typeTags: {
        enabled: true,
        applyOnUpload: true,
        animatedTag: "animated",
        videoTag: "video",
        tagCategory: "meta",
    },
    hash: {
        enabled: true,
        requestDelaySeconds: 2,
        userAgent: "szurubooru-autotag/1.0",
        applySafety: false,
        safetyOnlyIfUnset: true,
        categoryMap: {
            artist: "artist",
            character: "character",
            copyright: "copyright",
            meta: "meta",
            general: "general",
        },
        sources: {
            rule34: { enabled: true, priority: 1, apiKey: false, userId: "" },
            danbooru: { enabled: true, priority: 2, login: "", apiKey: false },
            gelbooru: {
                enabled: false,
                priority: 3,
                apiKey: false,
                userId: "",
            },
        },
    },
    ai: {
        enabled: false,
        url: "",
        token: false,
        generalThreshold: 0.35,
        characterThreshold: 0.75,
        resize: true,
    },
};

function _isPlainObject(value) {
    return (
        typeof value === "object" && value !== null && !Array.isArray(value)
    );
}

// merge a (possibly old-shaped) server config onto the defaults; a wrong-shaped
// branch (e.g. old list `sources`) falls back to the default for that branch
function _mergeDefaults(def, cfg) {
    if (!_isPlainObject(def)) {
        return cfg === undefined ? def : cfg;
    }
    if (!_isPlainObject(cfg)) {
        return JSON.parse(JSON.stringify(def));
    }
    const out = {};
    for (let key of Object.keys(def)) {
        out[key] = _mergeDefaults(def[key], cfg[key]);
    }
    for (let key of Object.keys(cfg)) {
        if (!(key in out)) {
            out[key] = cfg[key];
        }
    }
    return out;
}

class AutoTagController {
    constructor() {
        if (!api.hasPrivilege("posts:autoTag")) {
            this._view = new EmptyView();
            this._view.showError("You don't have privileges to auto-tag.");
            return;
        }

        topNavigation.activate("auto-tag");
        topNavigation.setTitle("Auto-tag");

        Promise.all([
            api.get(uri.formatApiLink("auto-tag", "config")),
            api.get(uri.formatApiLink("auto-tag", "job")),
        ]).then(
            ([configResponse, jobResponse]) => {
                this._view = new AutoTagView({
                    config: _mergeDefaults(
                        CONFIG_DEFAULTS,
                        configResponse.config
                    ),
                    job: jobResponse.job,
                });
                this._view.addEventListener("saveSettings", (e) =>
                    this._evtSaveSettings(e)
                );
                this._view.addEventListener("startJob", (e) =>
                    this._evtStartJob(e)
                );
                this._view.addEventListener("pauseJob", () =>
                    this._control("pause")
                );
                this._view.addEventListener("resumeJob", () =>
                    this._control("resume")
                );
                this._view.addEventListener("cancelJob", () =>
                    this._control("cancel")
                );
                this._maybePoll(jobResponse.job);
            },
            (error) => {
                this._view = new EmptyView();
                this._view.showError(error.message);
            }
        );
    }

    _evtSaveSettings(e) {
        api.put(uri.formatApiLink("auto-tag", "config"), {
            config: e.detail.config,
        }).then(
            () => {
                this._view.clearMessages();
                this._view.showSuccess("Settings saved.");
            },
            (error) => {
                this._view.clearMessages();
                this._view.showError(error.message);
            }
        );
    }

    _evtStartJob(e) {
        this._view.clearMessages();
        api.post(uri.formatApiLink("auto-tag", "job"), e.detail).then(
            (response) => {
                this._view.updateJob(response.job);
                this._maybePoll(response.job);
            },
            (error) => this._view.showError(error.message)
        );
    }

    _control(action) {
        api.post(uri.formatApiLink("auto-tag", "job", action), {}).then(
            (response) => {
                this._view.updateJob(response.job);
                this._maybePoll(response.job);
            },
            (error) => this._view.showError(error.message)
        );
    }

    _maybePoll(job) {
        if (this._timer) {
            clearTimeout(this._timer);
            this._timer = null;
        }
        if (!job || !ACTIVE.includes(job.status)) {
            return;
        }
        this._timer = setTimeout(() => this._poll(), 2000);
    }

    _poll() {
        // stop once the user has navigated away from the auto-tag page
        if (!document.getElementById("auto-tag")) {
            return;
        }
        api.get(uri.formatApiLink("auto-tag", "job")).then(
            (response) => {
                this._view.updateJob(response.job);
                this._maybePoll(response.job);
            },
            () => this._maybePoll({ status: "running" })
        );
    }
}

module.exports = (router) => {
    router.enter(["auto-tag"], (ctx, next) => {
        ctx.controller = new AutoTagController();
    });
};
