"use strict";

const events = require("../events.js");
const views = require("../util/views.js");

const template = views.getTemplate("auto-tag");

const ACTIVE = ["running", "paused", "cancelling"];
const METHODS = ["type_tags", "hash", "ai"];

function _setPath(obj, dotted, value) {
    const parts = dotted.split(".");
    let node = obj;
    for (let i = 0; i < parts.length - 1; i++) {
        node[parts[i]] = node[parts[i]] || {};
        node = node[parts[i]];
    }
    node[parts[parts.length - 1]] = value;
}

function _getPath(obj, dotted) {
    let node = obj;
    for (let part of dotted.split(".")) {
        if (node === null || typeof node !== "object") {
            return undefined;
        }
        node = node[part];
    }
    return node;
}

class AutoTagView extends events.EventTarget {
    constructor(ctx) {
        super();
        this._hostNode = document.getElementById("content-holder");
        views.replaceContent(
            this._hostNode,
            template({
                config: ctx.config,
                serverVersion: ctx.serverVersion,
            })
        );
        // szurubooru's template engine does not substitute a `<%- %>` in
        // attribute-name position, so bool checkboxes can't render their
        // `checked` state from the template - apply it from the config here.
        this._syncCheckboxes(ctx.config);
        views.syncScrollPosition();

        this._settingsFormNode.addEventListener("submit", (e) => {
            e.preventDefault();
            this.dispatchEvent(
                new CustomEvent("saveSettings", {
                    detail: { config: this._readConfig() },
                })
            );
        });
        this._runFormNode.addEventListener("submit", (e) => {
            e.preventDefault();
            this.dispatchEvent(
                new CustomEvent("startJob", { detail: this._readRun() })
            );
        });

        this.updateJob(ctx.job);
    }

    _syncCheckboxes(config) {
        for (let node of this._settingsFormNode.querySelectorAll(
            "[data-cfg][data-type=bool]"
        )) {
            node.checked = !!_getPath(config, node.dataset.cfg);
        }
    }

    get _settingsFormNode() {
        return this._hostNode.querySelector("form.auto-tag-settings");
    }

    get _runFormNode() {
        return this._hostNode.querySelector("form.auto-tag-run");
    }

    clearMessages() {
        views.clearMessages(this._hostNode);
    }

    showSuccess(text) {
        views.showSuccess(this._hostNode, text);
    }

    showError(text) {
        views.showError(this._hostNode, text);
    }

    _readConfig() {
        const config = {};
        for (let node of this._settingsFormNode.querySelectorAll(
            "[data-cfg]"
        )) {
            const path = node.dataset.cfg;
            const type = node.dataset.type || "string";
            let value;
            if (type === "bool") {
                value = node.checked;
            } else if (type === "number") {
                value = parseFloat(node.value);
                if (isNaN(value)) {
                    continue;
                }
            } else if (type === "list") {
                value = node.value
                    .split(/[\s,]+/)
                    .map((s) => s.trim())
                    .filter((s) => s);
            } else if (type === "secret") {
                // blank means "keep existing"; omit so the server keeps it
                if (!node.value) {
                    continue;
                }
                value = node.value;
            } else {
                value = node.value;
            }
            _setPath(config, path, value);
        }
        return config;
    }

    _readRun() {
        const methods = METHODS.filter(
            (m) => this._runFormNode.querySelector(`[name=m-${m}]`).checked
        );
        return {
            methods: methods,
            mode: this._runFormNode.querySelector("[name=mode]:checked").value,
            retryEmpty: this._runFormNode.querySelector("[name=retryEmpty]")
                .checked,
            query: this._runFormNode.querySelector("[name=query]").value,
        };
    }

    updateJob(job) {
        const node = this._hostNode.querySelector(".job-status");
        const startNode = this._runFormNode.querySelector(".start");
        const active = job && ACTIVE.includes(job.status);
        startNode.disabled = !!active;

        if (!job) {
            views.replaceContent(node, null);
            return;
        }

        const info = document.createElement("div");
        info.className = "info";
        let text = "Status: " + job.status;
        if (job.total) {
            text += " — " + job.processed + " / " + job.total;
        }
        info.textContent = text;

        const counts = document.createElement("div");
        counts.className = "counts";
        counts.textContent =
            "tagged " +
            job.tagged +
            ", errors " +
            job.errors +
            (job.currentPostId ? ", current @" + job.currentPostId : "");

        views.replaceContent(node, null);
        node.appendChild(info);
        node.appendChild(counts);
        if (job.message) {
            const msg = document.createElement("div");
            msg.className = "msg";
            msg.textContent = job.message;
            node.appendChild(msg);
        }

        if (active) {
            const controls = document.createElement("div");
            controls.className = "controls";
            if (job.status === "running") {
                controls.appendChild(this._controlButton("Pause", "pauseJob"));
            }
            if (job.status === "paused") {
                controls.appendChild(
                    this._controlButton("Resume", "resumeJob")
                );
            }
            controls.appendChild(this._controlButton("Cancel", "cancelJob"));
            node.appendChild(controls);
        }
    }

    _controlButton(label, eventType) {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = label;
        button.addEventListener("click", (e) => {
            e.preventDefault();
            this.dispatchEvent(new CustomEvent(eventType, { detail: {} }));
        });
        return button;
    }
}

module.exports = AutoTagView;
