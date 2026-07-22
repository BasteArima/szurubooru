"use strict";

const api = require("../api.js");
const uri = require("../util/uri.js");
const topNavigation = require("../models/top_navigation.js");
const AutoTagView = require("../views/auto_tag_view.js");
const EmptyView = require("../views/empty_view.js");

const ACTIVE = ["running", "paused", "cancelling"];

class AutoTagController {
    constructor() {
        if (!api.hasPrivilege("posts:auto_tag")) {
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
                    config: configResponse.config,
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
