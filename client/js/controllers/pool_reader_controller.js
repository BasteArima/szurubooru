"use strict";

const api = require("../api.js");
const Pool = require("../models/pool.js");
const topNavigation = require("../models/top_navigation.js");
const PoolReaderView = require("../views/pool_reader_view.js");
const EmptyView = require("../views/empty_view.js");

class PoolReaderController {
    constructor(ctx) {
        if (!api.hasPrivilege("pools:view")) {
            this._view = new EmptyView();
            this._view.showError("You don't have privileges to view pools.");
            return;
        }

        Pool.get(ctx.parameters.id).then(
            (pool) => {
                topNavigation.activate("pools");
                topNavigation.setTitle("Reading " + pool.names[0]);
                this._view = new PoolReaderView({
                    pool: pool,
                    initialPage: parseInt(ctx.parameters.page) || 1,
                });
            },
            (error) => {
                this._view = new EmptyView();
                this._view.showError(error.message);
            }
        );
    }
}

module.exports = (router) => {
    router.enter(["pool", ":id", "read"], (ctx, next) => {
        ctx.controller = new PoolReaderController(ctx);
    });
};
