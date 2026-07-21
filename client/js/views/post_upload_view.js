"use strict";

const events = require("../events.js");
const api = require("../api.js");
const misc = require("../util/misc.js");
const views = require("../util/views.js");
const settings = require("../models/settings.js");
const FileDropperControl = require("../controls/file_dropper_control.js");
const TagAutoCompleteControl = require("../controls/tag_auto_complete_control.js");

const defaultUploadSettings = {
    skipDuplicates: false,
    alwaysUploadSimilar: false,
    autoRelateSimilar: false,
    autoRelateThreshold: 60,
    pauseRemainOnError: true,
    defaultSafety: "safe",
    optionsOpen: false,
};

function _uploadSettings() {
    return Object.assign(
        {},
        defaultUploadSettings,
        settings.get().upload || {}
    );
}

function _formatFileSize(bytes) {
    if (!bytes) {
        return "";
    }
    const units = ["B", "KB", "MB", "GB"];
    let value = bytes;
    let unit = 0;
    while (value >= 1024 && unit < units.length - 1) {
        value /= 1024;
        unit++;
    }
    return (unit === 0 ? value : value.toFixed(1)) + " " + units[unit];
}

function _tagsFromName(name) {
    return (name || "")
        .replace(/\.[^.]+$/, "")
        .split(/[\s_\-.,()\[\]]+/)
        .map((token) => token.trim().toLowerCase())
        .filter((token) => token.length > 1 && !/^\d+$/.test(token));
}

const template = views.getTemplate("post-upload");
const rowTemplate = views.getTemplate("post-upload-row");

function _mimeTypeToPostType(mimeType) {
    return (
        {
            "application/x-shockwave-flash": "flash",
            "image/gif": "image",
            "image/jpeg": "image",
            "image/png": "image",
            "image/webp": "image",
            "image/bmp": "image",
            "image/avif": "image",
            "image/heif": "image",
            "image/heic": "image",
            "video/mp4": "video",
            "video/webm": "video",
            "video/quicktime": "video",
        }[mimeType] || "unknown"
    );
}

class Uploadable extends events.EventTarget {
    constructor() {
        super();
        this.lookalikes = [];
        this.lookalikesConfirmed = false;
        this.safety = _uploadSettings().defaultSafety;
        this.flags = [];
        this.tags = [];
        this.relations = [];
        this.selected = false;
        this.width = null;
        this.height = null;
        this.anonymous = !api.isLoggedIn();
        this.forceAnonymous = !api.isLoggedIn();
    }

    destroy() {}

    get size() {
        return null;
    }

    get mimeType() {
        return "application/octet-stream";
    }

    get type() {
        return _mimeTypeToPostType(this.mimeType);
    }

    get key() {
        throw new Error("Not implemented");
    }

    get name() {
        throw new Error("Not implemented");
    }
}

class File extends Uploadable {
    constructor(file) {
        super();
        this.file = file;

        this._previewUrl = null;
        if (URL && URL.createObjectURL) {
            this._previewUrl = URL.createObjectURL(file);
        } else {
            let reader = new FileReader();
            reader.readAsDataURL(file);
            reader.addEventListener("load", (e) => {
                this._previewUrl = e.target.result;
                this.dispatchEvent(
                    new CustomEvent("finish", { detail: { uploadable: this } })
                );
            });
        }
    }

    destroy() {
        if (URL && URL.createObjectURL && URL.revokeObjectURL) {
            URL.revokeObjectURL(this._previewUrl);
        }
    }

    get mimeType() {
        return this.file.type;
    }

    get size() {
        return this.file.size;
    }

    get previewUrl() {
        return this._previewUrl;
    }

    get key() {
        return this.file.name + this.file.size;
    }

    get name() {
        return this.file.name;
    }
}

class Url extends Uploadable {
    constructor(url) {
        super();
        this.url = url;
        this.dispatchEvent(new CustomEvent("finish"));
    }

    get mimeType() {
        let mime = {
            swf: "application/x-shockwave-flash",
            jpg: "image/jpeg",
            png: "image/png",
            gif: "image/gif",
            webp: "image/webp",
            bmp: "image/bmp",
            avif: "image/avif",
            heif: "image/heif",
            heic: "image/heic",
            mp4: "video/mp4",
            mov: "video/quicktime",
            webm: "video/webm",
        };
        for (let extension of Object.keys(mime)) {
            if (this.url.toLowerCase().indexOf("." + extension) !== -1) {
                return mime[extension];
            }
        }
        return "unknown";
    }

    get previewUrl() {
        return this.url;
    }

    get key() {
        return this.url;
    }

    get name() {
        return this.url;
    }
}

class PostUploadView extends events.EventTarget {
    constructor(ctx) {
        super();
        this._ctx = ctx;
        this._hostNode = document.getElementById("content-holder");

        views.replaceContent(this._hostNode, template());
        views.syncScrollPosition();

        this._cancelButtonNode.disabled = true;

        this._uploadables = [];
        this._uploadables.find = (u) => {
            return this._uploadables.findIndex((u2) => u.key === u2.key);
        };

        this._contentFileDropper = new FileDropperControl(
            this._contentInputNode,
            {
                extraText:
                    "Allowed extensions: .jpg, .png, .gif, .webm, .mp4, .swf, .avif, .heif, .heic",
                allowUrls: true,
                allowMultiple: true,
                lock: false,
            }
        );
        this._contentFileDropper.addEventListener("fileadd", (e) =>
            this._evtFilesAdded(e)
        );
        this._contentFileDropper.addEventListener("urladd", (e) =>
            this._evtUrlsAdded(e)
        );

        this._cancelButtonNode.addEventListener("click", (e) =>
            this._evtCancelButtonClick(e)
        );
        this._formNode.addEventListener("submit", (e) =>
            this._evtFormSubmit(e)
        );
        this._formNode.classList.add("inactive");

        this._lastSelectedIndex = null;
        this._draggedUploadable = null;

        this._installTagAutoComplete(this._allTagsInputNode);
        this._applyStoredSettings();
        this._installSettingPersistence();
        this._installBulkActions();
        this._refreshSelectionInfo();
    }

    _applyStoredSettings() {
        const stored = _uploadSettings();
        this._skipDuplicatesCheckboxNode.checked = stored.skipDuplicates;
        this._alwaysUploadSimilarCheckboxNode.checked =
            stored.alwaysUploadSimilar;
        this._autoRelateSimilarCheckboxNode.checked = stored.autoRelateSimilar;
        this._autoRelateThresholdInputNode.value = stored.autoRelateThreshold;
        this._pauseRemainOnErrorCheckboxNode.checked =
            stored.pauseRemainOnError;

        const optionsNode = this._hostNode.querySelector(".upload-options");
        if (optionsNode) {
            optionsNode.classList.toggle("open", !!stored.optionsOpen);
        }
        this._updateDefaultSafetyUI(stored.defaultSafety);
    }

    _saveUploadSettings(changes) {
        settings.save(
            { upload: Object.assign(_uploadSettings(), changes) },
            true
        );
    }

    _installSettingPersistence() {
        const persist = () =>
            this._saveUploadSettings({
                skipDuplicates: this._skipDuplicatesCheckboxNode.checked,
                alwaysUploadSimilar:
                    this._alwaysUploadSimilarCheckboxNode.checked,
                autoRelateSimilar:
                    this._autoRelateSimilarCheckboxNode.checked,
                autoRelateThreshold:
                    parseFloat(this._autoRelateThresholdInputNode.value) || 60,
                pauseRemainOnError:
                    this._pauseRemainOnErrorCheckboxNode.checked,
            });
        for (let node of [
            this._skipDuplicatesCheckboxNode,
            this._alwaysUploadSimilarCheckboxNode,
            this._autoRelateSimilarCheckboxNode,
            this._autoRelateThresholdInputNode,
            this._pauseRemainOnErrorCheckboxNode,
        ]) {
            node.addEventListener("change", persist);
        }
    }

    _installBulkActions() {
        const optionsNode = this._hostNode.querySelector(".upload-options");
        const optionsToggleNode =
            optionsNode && optionsNode.querySelector(".upload-options-toggle");
        if (optionsToggleNode) {
            optionsToggleNode.addEventListener("click", (e) => {
                e.preventDefault();
                const open = !optionsNode.classList.contains("open");
                optionsNode.classList.toggle("open", open);
                this._saveUploadSettings({ optionsOpen: open });
            });
        }

        for (let node of this._hostNode.querySelectorAll(
            ".default-safety [data-safety]"
        )) {
            node.addEventListener("click", (e) => {
                e.preventDefault();
                this._applySafetyToAll(node.dataset.safety);
            });
        }

        const bulkNode = this._hostNode.querySelector(".bulk-strip");
        if (!bulkNode) {
            return;
        }

        bulkNode.querySelector(".select-all").addEventListener("click", (e) => {
            e.preventDefault();
            for (let uploadable of this._uploadables) {
                this._setSelected(uploadable, true);
            }
            this._refreshSelectionInfo();
        });

        bulkNode
            .querySelector(".select-none")
            .addEventListener("click", (e) => {
                e.preventDefault();
                for (let uploadable of this._uploadables) {
                    this._setSelected(uploadable, false);
                }
                this._lastSelectedIndex = null;
                this._refreshSelectionInfo();
            });

        for (let node of bulkNode.querySelectorAll(
            ".selection-safety [data-safety]"
        )) {
            node.addEventListener("click", (e) => {
                e.preventDefault();
                this._applySafetyTo(
                    this._selectedUploadables(),
                    node.dataset.safety
                );
            });
        }

        bulkNode
            .querySelector(".bulk-tags-apply")
            .addEventListener("click", (e) => {
                e.preventDefault();
                this._applyBulkTags();
            });

        bulkNode
            .querySelector(".bulk-tags-filename")
            .addEventListener("click", (e) => {
                e.preventDefault();
                this._applyTagsFromFilename();
            });

        bulkNode
            .querySelector(".bulk-remove")
            .addEventListener("click", (e) => {
                e.preventDefault();
                this._removeTargets();
            });

        bulkNode.querySelector(".clear-list").addEventListener("click", (e) => {
            e.preventDefault();
            if (this._uploading || !this._uploadables.length) {
                return;
            }
            if (
                !window.confirm(
                    `Remove all ${this._uploadables.length} files from the ` +
                        "upload list?"
                )
            ) {
                return;
            }
            for (let uploadable of [...this._uploadables]) {
                this.removeUploadable(uploadable);
            }
            this._refreshSelectionInfo();
        });

        this._installTagAutoComplete(
            bulkNode.querySelector("[name=bulk-tags]")
        );
    }

    _selectedUploadables() {
        return this._uploadables.filter((u) => u.selected);
    }

    _setSelected(uploadable, value) {
        uploadable.selected = value;
        if (uploadable.rowNode) {
            uploadable.rowNode.classList.toggle("selected", value);
        }
    }

    _refreshSelectionInfo() {
        const bulkNode = this._hostNode.querySelector(".bulk-strip");
        if (!bulkNode) {
            return;
        }
        const selected = this._selectedUploadables().length;
        const total = this._uploadables.length;
        const infoNode = bulkNode.querySelector(".selection-info");
        if (infoNode) {
            infoNode.textContent = selected
                ? `${selected} of ${total} selected`
                : `${total} file(s) — click a row to select`;
        }
        // the per-selection actions only make sense with a selection
        bulkNode.classList.toggle("has-selection", selected > 0);
    }

    _applySafetyTo(uploadables, safety) {
        if (this._uploading) {
            return;
        }
        for (let uploadable of uploadables) {
            uploadable.safety = safety;
            const node =
                uploadable.rowNode &&
                uploadable.rowNode.querySelector(
                    `.safety input[value="${safety}"]`
                );
            if (node) {
                node.checked = true;
            }
        }
    }

    _applySafetyToAll(safety) {
        if (this._uploading) {
            return;
        }
        this._applySafetyTo(this._uploadables, safety);
        // also becomes the default for files added later
        this._saveUploadSettings({ defaultSafety: safety });
        this._updateDefaultSafetyUI(safety);
    }

    _updateDefaultSafetyUI(safety) {
        for (let node of this._hostNode.querySelectorAll(
            ".default-safety [data-safety]"
        )) {
            node.classList.toggle("active", node.dataset.safety === safety);
        }
    }

    _appendRowTags(uploadable, tags) {
        const node =
            uploadable.rowNode &&
            uploadable.rowNode.querySelector(".tags-input");
        if (!node) {
            return;
        }
        const merged = [
            ...new Set(misc.splitByWhitespace(node.value).concat(tags)),
        ];
        node.value = merged.join(" ");
        uploadable.tags = merged;
    }

    _applyBulkTags() {
        if (this._uploading) {
            return;
        }
        const inputNode = this._hostNode.querySelector("[name=bulk-tags]");
        const tags = inputNode ? misc.splitByWhitespace(inputNode.value) : [];
        if (!tags.length) {
            return;
        }
        for (let uploadable of this._selectedUploadables()) {
            this._appendRowTags(uploadable, tags);
        }
        inputNode.value = "";
    }

    _applyTagsFromFilename() {
        if (this._uploading) {
            return;
        }
        for (let uploadable of this._selectedUploadables()) {
            this._appendRowTags(uploadable, _tagsFromName(uploadable.name));
        }
    }

    _removeTargets() {
        if (this._uploading) {
            return;
        }
        // deliberately selection-only: removing everything is what the
        // explicit "Clear list" action is for
        const selected = this._selectedUploadables();
        if (!selected.length) {
            return;
        }
        for (let uploadable of selected) {
            this.removeUploadable(uploadable);
        }
        this._refreshSelectionInfo();
    }

    updateProgress(done, total) {
        const node = this._hostNode.querySelector(".progress");
        if (node) {
            node.textContent = total ? `Uploaded ${done} / ${total}` : "";
        }
    }

    setUploadableStatus(uploadable, status) {
        if (!uploadable || !uploadable.rowNode) {
            return;
        }
        const node = uploadable.rowNode.querySelector(".status");
        if (node) {
            node.textContent =
                { uploading: "Uploading…", error: "Needs attention" }[
                    status
                ] || "";
        }
        uploadable.rowNode.classList.toggle(
            "row-uploading",
            status === "uploading"
        );
    }

    _installTagAutoComplete(inputNode) {
        if (!inputNode) {
            return;
        }
        const control = new TagAutoCompleteControl(inputNode, {
            confirm: (tag) =>
                control.replaceSelectedText(tag.names[0], false),
        });
        // Enter in a tag field must not implicitly submit the form (which would
        // start the upload); the autocomplete still handles Enter to confirm.
        inputNode.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
            }
        });
    }

    enableForm() {
        views.enableForm(this._formNode);
        this._cancelButtonNode.disabled = true;
        this._formNode.classList.remove("uploading");
    }

    disableForm() {
        views.disableForm(this._formNode);
        this._cancelButtonNode.disabled = false;
        this._formNode.classList.add("uploading");
    }

    clearMessages() {
        views.clearMessages(this._hostNode);
    }

    showSuccess(message) {
        views.showSuccess(this._hostNode, message);
    }

    showError(message, uploadable) {
        this._showMessage(views.showError, message, uploadable);
    }

    showInfo(message, uploadable) {
        this._showMessage(views.showInfo, message, uploadable);
        views.appendExclamationMark();
    }

    _showMessage(functor, message, uploadable) {
        functor(uploadable ? uploadable.rowNode : this._hostNode, message);
    }

    addUploadables(uploadables) {
        this._formNode.classList.remove("inactive");
        let duplicatesFound = 0;
        for (let uploadable of uploadables) {
            if (this._uploadables.find(uploadable) !== -1) {
                duplicatesFound++;
                continue;
            }
            this._uploadables.push(uploadable);
            this._emit("change");
            this._renderRowNode(uploadable);
            uploadable.addEventListener("finish", (e) =>
                this._updateThumbnailNode(e.detail.uploadable)
            );
        }
        if (duplicatesFound) {
            let message = null;
            if (duplicatesFound < uploadables.length) {
                message =
                    "Some of the files were already added " +
                    "and have been skipped.";
            } else if (duplicatesFound === 1) {
                message = "This file was already added.";
            } else {
                message = "These files were already added.";
            }
            alert(message);
        }
        this._refreshSelectionInfo();
    }

    removeUploadable(uploadable) {
        if (this._uploadables.find(uploadable) === -1) {
            return;
        }
        uploadable.destroy();
        uploadable.rowNode.parentNode.removeChild(uploadable.rowNode);
        this._uploadables.splice(this._uploadables.find(uploadable), 1);
        this._emit("change");
        this._lastSelectedIndex = null;
        this._refreshSelectionInfo();
        if (!this._uploadables.length) {
            this._formNode.classList.add("inactive");
            this._submitButtonNode.value = "Upload all";
        }
    }

    updateUploadable(uploadable) {
        uploadable.lookalikesConfirmed = true;
        this._renderRowNode(uploadable);
    }

    _evtFilesAdded(e) {
        this.addUploadables(e.detail.files.map((file) => new File(file)));
    }

    _evtUrlsAdded(e) {
        this.addUploadables(e.detail.urls.map((url) => new Url(url)));
    }

    _evtCancelButtonClick(e) {
        e.preventDefault();
        this._emit("cancel");
    }

    _evtFormSubmit(e) {
        e.preventDefault();
        for (let uploadable of this._uploadables) {
            this._updateUploadableFromDom(uploadable);
        }
        this._submitButtonNode.value = "Resume";
        this._emit("submit");
    }

    _updateUploadableFromDom(uploadable) {
        const rowNode = uploadable.rowNode;

        const safetyNode = rowNode.querySelector(".safety input:checked");
        if (safetyNode) {
            uploadable.safety = safetyNode.value;
        }

        const anonymousNode = rowNode.querySelector(
            ".anonymous input:checked"
        );
        if (anonymousNode) {
            uploadable.anonymous = true;
        }

        const tagsNode = rowNode.querySelector(".tags-input");
        uploadable.tags = tagsNode
            ? misc.splitByWhitespace(tagsNode.value)
            : [];
        uploadable.relations = [];
        for (let [i, lookalike] of uploadable.lookalikes.entries()) {
            let lookalikeNode = rowNode.querySelector(
                `.lookalikes li:nth-child(${i + 1})`
            );
            if (lookalikeNode.querySelector("[name=copy-tags]").checked) {
                uploadable.tags = uploadable.tags.concat(
                    lookalike.post.tagNames
                );
            }
            if (lookalikeNode.querySelector("[name=add-relation]").checked) {
                uploadable.relations.push(lookalike.post.id);
            }
        }
        uploadable.tags = [...new Set(uploadable.tags)];
    }

    _evtRemoveClick(e, uploadable) {
        e.preventDefault();
        if (this._uploading) {
            return;
        }
        this.removeUploadable(uploadable);
    }

    _evtMoveClick(e, uploadable, delta) {
        e.preventDefault();
        if (this._uploading) {
            return;
        }
        let index = this._uploadables.find(uploadable);
        if ((index + delta).between(-1, this._uploadables.length)) {
            let uploadable1 = this._uploadables[index];
            let uploadable2 = this._uploadables[index + delta];
            this._uploadables[index] = uploadable2;
            this._uploadables[index + delta] = uploadable1;
            if (delta === 1) {
                this._listNode.insertBefore(
                    uploadable2.rowNode,
                    uploadable1.rowNode
                );
            } else {
                this._listNode.insertBefore(
                    uploadable1.rowNode,
                    uploadable2.rowNode
                );
            }
        }
    }

    _emit(eventType) {
        this.dispatchEvent(
            new CustomEvent(eventType, {
                detail: {
                    uploadables: this._uploadables,
                    skipDuplicates: this._skipDuplicatesCheckboxNode.checked,
                    alwaysUploadSimilar:
                        this._alwaysUploadSimilarCheckboxNode.checked,
                    autoRelateSimilar:
                        this._autoRelateSimilarCheckboxNode.checked,
                    autoRelateThreshold:
                        this._autoRelateThresholdInputNode.value,
                    pauseRemainOnError:
                        this._pauseRemainOnErrorCheckboxNode.checked,
                    globalTags: this._allTagsInputNode
                        ? misc.splitByWhitespace(this._allTagsInputNode.value)
                        : [],
                },
            })
        );
    }

    _renderRowNode(uploadable) {
        const rowNode = rowTemplate(
            Object.assign({}, this._ctx, { uploadable: uploadable })
        );
        if (uploadable.rowNode) {
            uploadable.rowNode.parentNode.replaceChild(
                rowNode,
                uploadable.rowNode
            );
        } else {
            this._listNode.appendChild(rowNode);
        }

        uploadable.rowNode = rowNode;

        rowNode
            .querySelector("a.remove")
            .addEventListener("click", (e) =>
                this._evtRemoveClick(e, uploadable)
            );
        rowNode
            .querySelector("a.move-up")
            .addEventListener("click", (e) =>
                this._evtMoveClick(e, uploadable, -1)
            );
        rowNode
            .querySelector("a.move-down")
            .addEventListener("click", (e) =>
                this._evtMoveClick(e, uploadable, 1)
            );

        this._installTagAutoComplete(rowNode.querySelector(".tags-input"));

        if (uploadable.selected) {
            rowNode.classList.add("selected");
        }
        rowNode.addEventListener("click", (e) =>
            this._evtRowClick(e, uploadable)
        );
        this._installDragAndDrop(rowNode, uploadable);
        this._installFileInfo(rowNode, uploadable);
    }

    _evtRowClick(e, uploadable) {
        if (this._uploading) {
            return;
        }
        // clicks meant for the row's own controls must not change the selection
        if (
            e.target.closest(
                "input, textarea, select, label, a, button, video"
            )
        ) {
            return;
        }
        const index = this._uploadables.find(uploadable);
        if (e.shiftKey && this._lastSelectedIndex !== null) {
            const from = Math.min(this._lastSelectedIndex, index);
            const to = Math.max(this._lastSelectedIndex, index);
            for (let i = from; i <= to; i++) {
                this._setSelected(this._uploadables[i], true);
            }
        } else if (e.ctrlKey || e.metaKey) {
            this._setSelected(uploadable, !uploadable.selected);
            this._lastSelectedIndex = index;
        } else {
            for (let other of this._uploadables) {
                this._setSelected(other, false);
            }
            this._setSelected(uploadable, true);
            this._lastSelectedIndex = index;
        }
        this._refreshSelectionInfo();
    }

    _installDragAndDrop(rowNode, uploadable) {
        const handleNode = rowNode.querySelector(".drag-handle");
        if (handleNode) {
            // only start a drag from the handle, so text selection inside the
            // row's inputs keeps working
            handleNode.addEventListener("mousedown", () => {
                rowNode.draggable = true;
            });
            handleNode.addEventListener("mouseup", () => {
                rowNode.draggable = false;
            });
        }

        rowNode.addEventListener("dragstart", (e) => {
            if (this._uploading) {
                e.preventDefault();
                return;
            }
            this._draggedUploadable = uploadable;
            rowNode.classList.add("dragging");
            if (e.dataTransfer) {
                e.dataTransfer.effectAllowed = "move";
                try {
                    e.dataTransfer.setData("text/plain", uploadable.key);
                } catch (error) {
                    // some browsers refuse custom data; the drag still works
                }
            }
        });

        rowNode.addEventListener("dragend", () => {
            rowNode.draggable = false;
            rowNode.classList.remove("dragging");
            this._draggedUploadable = null;
            for (let other of this._uploadables) {
                if (other.rowNode) {
                    other.rowNode.classList.remove("drop-target");
                }
            }
        });

        rowNode.addEventListener("dragover", (e) => {
            if (
                !this._draggedUploadable ||
                this._draggedUploadable === uploadable
            ) {
                return;
            }
            e.preventDefault();
            if (e.dataTransfer) {
                e.dataTransfer.dropEffect = "move";
            }
            rowNode.classList.add("drop-target");
        });

        rowNode.addEventListener("dragleave", () => {
            rowNode.classList.remove("drop-target");
        });

        rowNode.addEventListener("drop", (e) => {
            e.preventDefault();
            rowNode.classList.remove("drop-target");
            this._moveUploadableTo(this._draggedUploadable, uploadable);
        });
    }

    _moveUploadableTo(dragged, target) {
        if (!dragged || dragged === target) {
            return;
        }
        const from = this._uploadables.find(dragged);
        const to = this._uploadables.find(target);
        if (from === -1 || to === -1) {
            return;
        }
        this._uploadables.splice(from, 1);
        this._uploadables.splice(to, 0, dragged);
        if (from < to) {
            this._listNode.insertBefore(
                dragged.rowNode,
                target.rowNode.nextSibling
            );
        } else {
            this._listNode.insertBefore(dragged.rowNode, target.rowNode);
        }
    }

    _installFileInfo(rowNode, uploadable) {
        this._updateFileInfoNode(uploadable);
        if (uploadable.width) {
            return;
        }
        const imageNode = rowNode.querySelector(".thumbnail img");
        if (imageNode) {
            const onLoad = () => {
                if (imageNode.naturalWidth) {
                    uploadable.width = imageNode.naturalWidth;
                    uploadable.height = imageNode.naturalHeight;
                    this._updateFileInfoNode(uploadable);
                }
            };
            if (imageNode.complete) {
                onLoad();
            } else {
                imageNode.addEventListener("load", onLoad);
            }
        }
        const videoNode = rowNode.querySelector("video");
        if (videoNode) {
            videoNode.addEventListener("loadedmetadata", () => {
                uploadable.width = videoNode.videoWidth;
                uploadable.height = videoNode.videoHeight;
                this._updateFileInfoNode(uploadable);
            });
        }
    }

    _updateFileInfoNode(uploadable) {
        const node =
            uploadable.rowNode &&
            uploadable.rowNode.querySelector(".file-info");
        if (!node) {
            return;
        }
        const parts = [];
        if (uploadable.size) {
            parts.push(_formatFileSize(uploadable.size));
        }
        if (uploadable.width && uploadable.height) {
            parts.push(uploadable.width + "×" + uploadable.height);
        }
        node.textContent = parts.join(" · ");
    }

    _updateThumbnailNode(uploadable) {
        const rowNode = rowTemplate(
            Object.assign({}, this._ctx, { uploadable: uploadable })
        );
        views.replaceContent(
            uploadable.rowNode.querySelector(".thumbnail"),
            rowNode.querySelector(".thumbnail").childNodes
        );
    }

    get _uploading() {
        return this._formNode.classList.contains("uploading");
    }

    get _listNode() {
        return this._hostNode.querySelector(".uploadables-container");
    }

    get _formNode() {
        return this._hostNode.querySelector("form");
    }

    get _skipDuplicatesCheckboxNode() {
        return this._hostNode.querySelector("form [name=skip-duplicates]");
    }

    get _alwaysUploadSimilarCheckboxNode() {
        return this._hostNode.querySelector(
            "form [name=always-upload-similar]"
        );
    }

    get _autoRelateSimilarCheckboxNode() {
        return this._hostNode.querySelector("form [name=auto-relate-similar]");
    }

    get _autoRelateThresholdInputNode() {
        return this._hostNode.querySelector(
            "form [name=auto-relate-threshold]"
        );
    }

    get _pauseRemainOnErrorCheckboxNode() {
        return this._hostNode.querySelector(
            "form [name=pause-remain-on-error]"
        );
    }

    get _allTagsInputNode() {
        return this._hostNode.querySelector("form [name=all-tags]");
    }

    get _submitButtonNode() {
        return this._hostNode.querySelector("form [type=submit]");
    }

    get _cancelButtonNode() {
        return this._hostNode.querySelector("form .cancel");
    }

    get _contentInputNode() {
        return this._formNode.querySelector(".dropper-container");
    }
}

module.exports = PostUploadView;
