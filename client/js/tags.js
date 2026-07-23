"use strict";

const misc = require("./util/misc.js");
const TagCategoryList = require("./models/tag_category_list.js");

let _stylesheet = null;
// category names in display order (as returned by the API, i.e. by `order`),
// cached so views can group tags by category without an extra async call
let _categoryOrder = [];

function refreshCategoryColorMap() {
    return TagCategoryList.get().then((response) => {
        _categoryOrder = Array.from(response.results).map((c) => c.name);
        if (_stylesheet) {
            document.head.removeChild(_stylesheet);
        }
        _stylesheet = document.createElement("style");
        document.head.appendChild(_stylesheet);
        for (let category of response.results) {
            const ruleName = misc.makeCssName(category.name, "tag");
            _stylesheet.sheet.insertRule(
                `.${ruleName} { color: ${category.color} }`,
                _stylesheet.sheet.cssRules.length
            );
        }
    });
}

// ordered list of category names; empty until refreshCategoryColorMap resolves
function getCategoryOrder() {
    return _categoryOrder;
}

module.exports = {
    refreshCategoryColorMap: refreshCategoryColorMap,
    getCategoryOrder: getCategoryOrder,
};
