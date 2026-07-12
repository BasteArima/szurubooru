"use strict";

const views = require("../util/views.js");
const uri = require("../util/uri.js");
const keyboard = require("../util/keyboard.js");
const Touch = require("../util/touch.js");
const Post = require("../models/post.js");

const template = views.getTemplate("pool-reader");

const FIT_ORDER = ["fit-both", "fit-width", "fit-height"];

class PoolReaderView {
    constructor(ctx) {
        this._pool = ctx.pool;
        this._pages = ctx.pool.posts.map((post) => ({
            id: post.id,
            thumbnailUrl: post.thumbnailUrl,
            post: null,
            promise: null,
            continuousLoaded: false,
        }));
        this._mode = "paged"; // "paged" | "continuous"
        this._fit = "fit-both";
        this._index = Math.min(
            Math.max((ctx.initialPage || 1) - 1, 0),
            Math.max(this._pages.length - 1, 0)
        );
        this._loadObserver = null;
        this._currentObserver = null;

        this._hostNode = document.getElementById("content-holder");
        const readerNode = template({
            pool: this._pool,
            poolUrl: uri.formatClientLink("pool", this._pool.id),
        });
        this._readerNode = readerNode;
        views.replaceContent(this._hostNode, readerNode);

        this._bodyNode = readerNode.querySelector(".reader-body");
        this._counterNode = readerNode.querySelector(".reader-counter");
        this._modeButtonNode = readerNode.querySelector(".reader-mode");
        this._fitButtonNode = readerNode.querySelector(".reader-fit");
        this._fullscreenButtonNode =
            readerNode.querySelector(".reader-fullscreen");

        this._modeButtonNode.addEventListener("click", (e) =>
            this._evtToggleMode(e)
        );
        this._fitButtonNode.addEventListener("click", (e) =>
            this._evtCycleFit(e)
        );
        this._fullscreenButtonNode.addEventListener("click", (e) =>
            this._evtToggleFullscreen(e)
        );

        keyboard.bind(["a", "left"], () => this._goPrev());
        keyboard.bind(["d", "right"], () => this._goNext());

        // horizontal swipe pages; vertical is left for normal scrolling
        new Touch(
            this._bodyNode,
            () => this._goNext(),
            () => this._goPrev()
        );

        views.monitorNodeRemoval(this._readerNode, () => this._cleanup());

        if (!this._pages.length) {
            this._bodyNode.textContent = "This pool has no posts.";
            this._updateCounter();
            return;
        }
        this._render();
    }

    _cleanup() {
        for (let observer of [this._loadObserver, this._currentObserver]) {
            if (observer) {
                observer.disconnect();
            }
        }
        this._loadObserver = null;
        this._currentObserver = null;
    }

    _loadPage(index) {
        const page = this._pages[index];
        if (!page) {
            return Promise.resolve(null);
        }
        if (page.post) {
            return Promise.resolve(page.post);
        }
        if (!page.promise) {
            page.promise = Post.get(page.id).then((post) => {
                page.post = post;
                return post;
            });
        }
        return page.promise;
    }

    _render() {
        this._cleanup();
        this._fitButtonNode.style.display =
            this._mode === "paged" ? "" : "none";
        if (this._mode === "paged") {
            this._renderPaged();
        } else {
            this._renderContinuous();
        }
        this._updateCounter();
    }

    _updateCounter() {
        this._counterNode.textContent = this._pages.length
            ? `${this._index + 1} / ${this._pages.length}`
            : "";
    }

    // ------- paged mode -------

    _renderPaged() {
        const wrapNode = document.createElement("div");
        wrapNode.className = "reader-paged";

        this._pageNode = document.createElement("div");
        this._pageNode.className = "reader-page " + this._fit;

        const prevNode = document.createElement("a");
        prevNode.className = "reader-edge prev";
        prevNode.addEventListener("click", (e) => {
            e.preventDefault();
            this._goPrev();
        });

        const nextNode = document.createElement("a");
        nextNode.className = "reader-edge next";
        nextNode.addEventListener("click", (e) => {
            e.preventDefault();
            this._goNext();
        });

        wrapNode.appendChild(this._pageNode);
        wrapNode.appendChild(prevNode);
        wrapNode.appendChild(nextNode);
        views.replaceContent(this._bodyNode, wrapNode);

        this._showCurrentPage();
    }

    _showCurrentPage() {
        const index = this._index;
        views.replaceContent(this._pageNode, this._makeSpinner());
        this._loadPage(index).then((post) => {
            if (this._mode !== "paged" || this._index !== index || !post) {
                return;
            }
            views.replaceContent(this._pageNode, this._makeContentNode(post));
        });
        // preload the next page for snappy paging
        this._loadPage(index + 1);
    }

    // ------- continuous mode -------

    _renderContinuous() {
        for (let page of this._pages) {
            page.continuousLoaded = false;
        }

        const wrapNode = document.createElement("div");
        wrapNode.className = "reader-continuous";
        this._continuousNodes = [];
        for (let i = 0; i < this._pages.length; i++) {
            const pageNode = document.createElement("div");
            pageNode.className = "reader-cpage";
            pageNode.dataset.index = i;
            const placeholderNode = document.createElement("div");
            placeholderNode.className = "reader-placeholder";
            pageNode.appendChild(placeholderNode);
            wrapNode.appendChild(pageNode);
            this._continuousNodes.push(pageNode);
        }
        views.replaceContent(this._bodyNode, wrapNode);

        // lazily fetch page content as it approaches the viewport
        this._loadObserver = new IntersectionObserver(
            (entries) => {
                for (let entry of entries) {
                    if (entry.isIntersecting) {
                        this._loadContinuousPage(
                            parseInt(entry.target.dataset.index)
                        );
                    }
                }
            },
            { root: this._bodyNode, rootMargin: "1500px 0px" }
        );
        // track which page is currently centered for the counter
        this._currentObserver = new IntersectionObserver(
            (entries) => {
                for (let entry of entries) {
                    if (entry.isIntersecting) {
                        this._index = parseInt(entry.target.dataset.index);
                        this._updateCounter();
                    }
                }
            },
            { root: this._bodyNode, rootMargin: "-45% 0px -45% 0px" }
        );
        for (let node of this._continuousNodes) {
            this._loadObserver.observe(node);
            this._currentObserver.observe(node);
        }

        const target = this._continuousNodes[this._index];
        if (target) {
            target.scrollIntoView();
        }
    }

    _loadContinuousPage(index) {
        const page = this._pages[index];
        if (!page || page.continuousLoaded) {
            return;
        }
        page.continuousLoaded = true;
        const pageNode = this._continuousNodes[index];
        this._loadPage(index).then(
            (post) => {
                if (this._mode !== "continuous" || !post) {
                    return;
                }
                views.replaceContent(pageNode, this._makeContentNode(post));
            },
            () => {
                page.continuousLoaded = false;
            }
        );
    }

    // ------- navigation -------

    _goPrev() {
        if (this._index > 0) {
            this._index -= 1;
            this._afterNav();
        }
    }

    _goNext() {
        if (this._index < this._pages.length - 1) {
            this._index += 1;
            this._afterNav();
        }
    }

    _afterNav() {
        this._updateCounter();
        if (this._mode === "paged") {
            this._showCurrentPage();
        } else {
            const target = this._continuousNodes[this._index];
            if (target) {
                target.scrollIntoView({ behavior: "smooth" });
            }
        }
    }

    // ------- controls -------

    _evtToggleMode(e) {
        e.preventDefault();
        this._mode = this._mode === "paged" ? "continuous" : "paged";
        this._modeButtonNode.textContent =
            this._mode === "paged" ? "Continuous" : "Paged";
        this._render();
    }

    _evtCycleFit(e) {
        e.preventDefault();
        this._fit =
            FIT_ORDER[(FIT_ORDER.indexOf(this._fit) + 1) % FIT_ORDER.length];
        this._fitButtonNode.textContent =
            "Fit: " + this._fit.replace("fit-", "");
        if (this._mode === "paged" && this._pageNode) {
            this._pageNode.className = "reader-page " + this._fit;
        }
    }

    _evtToggleFullscreen(e) {
        e.preventDefault();
        if (!document.fullscreenElement) {
            if (this._readerNode.requestFullscreen) {
                this._readerNode.requestFullscreen();
            }
        } else if (document.exitFullscreen) {
            document.exitFullscreen();
        }
    }

    // ------- rendering helpers -------

    _makeContentNode(post) {
        let node;
        if (post.type === "video") {
            node = document.createElement("video");
            node.src = post.contentUrl;
            node.controls = true;
            node.loop = !!(post.flags && post.flags.includes("loop"));
            node.playsInline = true;
        } else {
            node = document.createElement("img");
            node.src = post.contentUrl;
            node.alt = "";
        }
        node.className = "reader-content";
        return node;
    }

    _makeSpinner() {
        const node = document.createElement("div");
        node.className = "reader-loading";
        node.textContent = "Loading…";
        return node;
    }
}

module.exports = PoolReaderView;
