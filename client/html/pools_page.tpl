<div class='pool-list'>
    <% if (ctx.response.results.length) { %>
        <div class='sort-bar'>
            Sort by:
            <a href='<%- ctx.formatClientLink('pools', {query: 'sort:name'}) %>'>name</a> &middot;
            <a href='<%- ctx.formatClientLink('pools', {query: 'sort:post-count'}) %>'>page count</a> &middot;
            <a href='<%- ctx.formatClientLink('pools', {query: 'sort:creation-time'}) %>'>newest</a>
        </div>
        <ul class='pool-grid'>
            <% for (let pool of ctx.response.results) { %>
                <li class='pool-card'>
                    <a class='cover' href='<%- pool.postCount ? ctx.formatClientLink('pool', pool.id, 'read') : ctx.formatClientLink('pool', pool.id) %>' title='<%- pool.names[0] %>'>
                        <% if (pool.posts.length) { %>
                            <%= ctx.makeThumbnail(pool.posts.at(0).thumbnailUrl) %>
                        <% } else { %>
                            <span class='thumbnail empty no-cover'></span>
                        <% } %>
                        <span class='page-count'><%- pool.postCount %></span>
                    </a>
                    <a class='title' href='<%- pool.postCount ? ctx.formatClientLink('pool', pool.id, 'read') : ctx.formatClientLink('pool', pool.id) %>'><%- pool.names[0] %></a>
                    <% if (pool.category && pool.category !== 'default') { %>
                        <span class='category <%= ctx.makeCssName(pool.category, 'pool') %>'><%- pool.category %></span>
                    <% } %>
                </li>
            <% } %>
        </ul>
    <% } else { %>
        <p class='no-pools'>No pools found.</p>
    <% } %>
</div>
