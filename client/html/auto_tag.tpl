<div class='content-wrapper' id='auto-tag'>
    <div class='messages'></div>
    <h1>Auto-tag</h1>

    <form class='auto-tag-settings'>
        <div class='settings-grid'>
            <fieldset>
                <legend>Type tags</legend>
                <div class='checks'>
                    <label class='inline'><input type='checkbox' data-cfg='typeTags.enabled' data-type='bool' <%- ctx.config.typeTags.enabled ? 'checked' : '' %>/><span class='checkbox'>Enabled</span></label>
                    <label class='inline'><input type='checkbox' data-cfg='typeTags.applyOnUpload' data-type='bool' <%- ctx.config.typeTags.applyOnUpload ? 'checked' : '' %>/><span class='checkbox'>Apply on upload</span></label>
                </div>
                <label class='field'><span>animated tag</span><input type='text' data-cfg='typeTags.animatedTag' value='<%- ctx.config.typeTags.animatedTag %>'/></label>
                <label class='field'><span>video tag</span><input type='text' data-cfg='typeTags.videoTag' value='<%- ctx.config.typeTags.videoTag %>'/></label>
                <label class='field'><span>tag category</span><input type='text' data-cfg='typeTags.tagCategory' value='<%- ctx.config.typeTags.tagCategory %>'/></label>
            </fieldset>

            <fieldset class='wide'>
                <legend>Hash lookup</legend>
                <div class='checks'>
                    <label class='inline'><input type='checkbox' data-cfg='hash.enabled' data-type='bool' <%- ctx.config.hash.enabled ? 'checked' : '' %>/><span class='checkbox'>Enabled</span></label>
                    <label class='inline'><input type='checkbox' data-cfg='hash.applySafety' data-type='bool' <%- ctx.config.hash.applySafety ? 'checked' : '' %>/><span class='checkbox'>Set safety from rating</span></label>
                    <label class='inline'><input type='checkbox' data-cfg='hash.safetyOnlyIfUnset' data-type='bool' <%- ctx.config.hash.safetyOnlyIfUnset ? 'checked' : '' %>/><span class='checkbox'>…only when still Safe</span></label>
                </div>
                <label class='field'><span>Sources</span><input type='text' data-cfg='hash.sources' data-type='list' value='<%- ctx.config.hash.sources.join(", ") %>'/></label>
                <label class='field'><span>Request delay, s</span><input type='number' step='0.1' min='0' data-cfg='hash.requestDelaySeconds' data-type='number' value='<%- ctx.config.hash.requestDelaySeconds %>'/></label>
                <label class='field'><span>User-Agent</span><input type='text' data-cfg='hash.userAgent' value='<%- ctx.config.hash.userAgent %>'/></label>
                <label class='field'><span>Danbooru login</span><input type='text' data-cfg='hash.danbooruLogin' value='<%- ctx.config.hash.danbooruLogin %>'/></label>
                <label class='field'><span>Danbooru API key</span><input type='password' autocomplete='off' data-cfg='hash.danbooruApiKey' data-type='secret' placeholder='<%- ctx.config.hash.danbooruApiKey ? "set — leave blank to keep" : "not set" %>'/></label>
                <p class='sources-hint'>rule34.xxx needs no credentials. Danbooru login+key is optional (higher limits).</p>
                <div class='category-map'>
                    <span class='sub'>Category mapping (booru → this site)</span>
                    <div class='map-grid'>
                        <% for (let key of ['artist', 'character', 'copyright', 'meta', 'general']) { %>
                            <label class='field small'><span><%- key %> →</span><input type='text' data-cfg='hash.categoryMap.<%- key %>' value='<%- ctx.config.hash.categoryMap[key] || "" %>'/></label>
                        <% } %>
                    </div>
                </div>
            </fieldset>

            <fieldset>
                <legend>AI tagger <span class='hint'>(second delivery — not active yet)</span></legend>
                <div class='checks'>
                    <label class='inline'><input type='checkbox' data-cfg='ai.enabled' data-type='bool' <%- ctx.config.ai.enabled ? 'checked' : '' %>/><span class='checkbox'>Enabled</span></label>
                </div>
                <label class='field'><span>Service URL</span><input type='text' data-cfg='ai.url' placeholder='http://192.168.0.XX:7860/tag' value='<%- ctx.config.ai.url %>'/></label>
                <label class='field'><span>Token</span><input type='password' autocomplete='off' data-cfg='ai.token' data-type='secret' placeholder='<%- ctx.config.ai.token ? "set — leave blank to keep" : "not set" %>'/></label>
                <label class='field'><span>General threshold</span><input type='number' step='0.01' min='0' max='1' data-cfg='ai.generalThreshold' data-type='number' value='<%- ctx.config.ai.generalThreshold %>'/></label>
                <label class='field'><span>Character threshold</span><input type='number' step='0.01' min='0' max='1' data-cfg='ai.characterThreshold' data-type='number' value='<%- ctx.config.ai.characterThreshold %>'/></label>
            </fieldset>
        </div>

        <input type='submit' value='Save settings'/>
    </form>

    <hr/>

    <form class='auto-tag-run'>
        <h2>Run</h2>

        <div class='row'>
            <span class='label'>Methods</span>
            <label class='inline'><input type='checkbox' name='m-type_tags' checked/><span class='checkbox'>Type tags</span></label>
            <label class='inline'><input type='checkbox' name='m-hash' checked/><span class='checkbox'>Hash</span></label>
            <label class='inline'><input type='checkbox' name='m-ai'/><span class='checkbox'>AI</span></label>
        </div>

        <div class='row'>
            <span class='label'>Posts</span>
            <label class='inline'><input type='radio' name='mode' value='new' checked/><span class='radio'>New only</span></label>
            <label class='inline'><input type='radio' name='mode' value='errors'/><span class='radio'>Retry failures</span></label>
            <label class='inline'><input type='radio' name='mode' value='all'/><span class='radio'>Everything</span></label>
        </div>

        <div class='row'>
            <span class='label'></span>
            <label class='inline'><input type='checkbox' name='retryEmpty'/><span class='checkbox'>Re-check hash "not found"</span></label>
        </div>

        <div class='row'>
            <span class='label'>Scope</span>
            <input type='text' name='query' placeholder='search query — empty = all posts'/>
        </div>

        <input type='submit' class='start' value='Start'/>
    </form>

    <div class='job-status'></div>
</div>
