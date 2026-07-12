"use strict";

const settings = require("../models/settings.js");
const views = require("../util/views.js");

const template = views.getTemplate("pools-page");

class PoolsPageView {
    constructor(ctx) {
        this._ctx = ctx;
        this._hostNode = ctx.hostNode;
        this._render();
    }

    _render() {
        const ctx = Object.assign({}, this._ctx, {
            settings: settings.get(),
        });
        views.replaceContent(this._hostNode, template(ctx));

        for (let node of this._hostNode.querySelectorAll(
            ".view-toggle [data-view]"
        )) {
            node.addEventListener("click", (e) => {
                e.preventDefault();
                settings.save({ poolsView: node.dataset.view }, true);
                this._render();
            });
        }
    }
}

module.exports = PoolsPageView;
