<div class='content-wrapper' id='auto-tag'>
    <div class='messages'></div>
    <h1>Auto-tag</h1>

    <form class='auto-tag-settings'>
        <h2>Settings</h2>

        <fieldset>
            <legend>Type tags</legend>
            <label class='inline'><input type='checkbox' data-cfg='typeTags.enabled' data-type='bool' <%- ctx.config.typeTags.enabled ? 'checked' : '' %>/> Enabled</label>
            <label class='inline'><input type='checkbox' data-cfg='typeTags.applyOnUpload' data-type='bool' <%- ctx.config.typeTags.applyOnUpload ? 'checked' : '' %>/> Apply on upload</label>
            <label>animated tag <input type='text' data-cfg='typeTags.animatedTag' value='<%- ctx.config.typeTags.animatedTag %>'/></label>
            <label>video tag <input type='text' data-cfg='typeTags.videoTag' value='<%- ctx.config.typeTags.videoTag %>'/></label>
            <label>tag category <input type='text' data-cfg='typeTags.tagCategory' value='<%- ctx.config.typeTags.tagCategory %>'/></label>
        </fieldset>

        <fieldset>
            <legend>Hash lookup</legend>
            <label class='inline'><input type='checkbox' data-cfg='hash.enabled' data-type='bool' <%- ctx.config.hash.enabled ? 'checked' : '' %>/> Enabled</label>
            <label>Sources (priority order, comma-separated) <input type='text' data-cfg='hash.sources' data-type='list' value='<%- ctx.config.hash.sources.join(", ") %>'/></label>
            <label>Request delay, seconds <input type='number' step='0.1' min='0' data-cfg='hash.requestDelaySeconds' data-type='number' value='<%- ctx.config.hash.requestDelaySeconds %>'/></label>
            <label>User-Agent (Danbooru bans generic ones) <input type='text' data-cfg='hash.userAgent' value='<%- ctx.config.hash.userAgent %>'/></label>
            <label>Danbooru login <input type='text' data-cfg='hash.danbooruLogin' value='<%- ctx.config.hash.danbooruLogin %>'/></label>
            <label>Danbooru API key <input type='password' autocomplete='off' data-cfg='hash.danbooruApiKey' data-type='secret' placeholder='<%- ctx.config.hash.danbooruApiKey ? "set — leave blank to keep" : "not set" %>'/></label>
            <label class='inline'><input type='checkbox' data-cfg='hash.applySafety' data-type='bool' <%- ctx.config.hash.applySafety ? 'checked' : '' %>/> Set safety from booru rating</label>
            <label class='inline'><input type='checkbox' data-cfg='hash.safetyOnlyIfUnset' data-type='bool' <%- ctx.config.hash.safetyOnlyIfUnset ? 'checked' : '' %>/> …only when the post is still Safe</label>
            <div class='category-map'>
                <span class='label'>Category mapping (booru → this site)</span>
                <% for (let key of ['artist', 'character', 'copyright', 'meta', 'general']) { %>
                    <label class='inline'><%- key %> → <input type='text' data-cfg='hash.categoryMap.<%- key %>' value='<%- ctx.config.hash.categoryMap[key] || "" %>'/></label>
                <% } %>
            </div>
        </fieldset>

        <fieldset>
            <legend>AI tagger <span class='hint'>(second delivery — not active yet)</span></legend>
            <label class='inline'><input type='checkbox' data-cfg='ai.enabled' data-type='bool' <%- ctx.config.ai.enabled ? 'checked' : '' %>/> Enabled</label>
            <label>Service URL <input type='text' data-cfg='ai.url' placeholder='http://192.168.0.XX:7860/tag' value='<%- ctx.config.ai.url %>'/></label>
            <label>Token <input type='password' autocomplete='off' data-cfg='ai.token' data-type='secret' placeholder='<%- ctx.config.ai.token ? "set — leave blank to keep" : "not set" %>'/></label>
            <label>General threshold <input type='number' step='0.01' min='0' max='1' data-cfg='ai.generalThreshold' data-type='number' value='<%- ctx.config.ai.generalThreshold %>'/></label>
            <label>Character threshold <input type='number' step='0.01' min='0' max='1' data-cfg='ai.characterThreshold' data-type='number' value='<%- ctx.config.ai.characterThreshold %>'/></label>
        </fieldset>

        <input type='submit' value='Save settings'/>
    </form>

    <hr/>

    <form class='auto-tag-run'>
        <h2>Run</h2>

        <div class='row'>
            <span class='label'>Methods</span>
            <label class='inline'><input type='checkbox' name='m-type_tags' checked/> Type tags</label>
            <label class='inline'><input type='checkbox' name='m-hash' checked/> Hash</label>
            <label class='inline'><input type='checkbox' name='m-ai'/> AI</label>
        </div>

        <div class='row'>
            <span class='label'>Posts</span>
            <label class='inline'><input type='radio' name='mode' value='new' checked/> New only</label>
            <label class='inline'><input type='radio' name='mode' value='errors'/> Retry failures</label>
            <label class='inline'><input type='radio' name='mode' value='all'/> Everything</label>
        </div>

        <div class='row'>
            <label class='inline'><input type='checkbox' name='retryEmpty'/> Re-check hash "not found"</label>
        </div>

        <div class='row'>
            <label>Scope (search query; empty = all posts) <input type='text' name='query'/></label>
        </div>

        <input type='submit' class='start' value='Start'/>
    </form>

    <div class='job-status'></div>
</div>
