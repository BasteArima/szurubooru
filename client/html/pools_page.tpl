<div class='pool-list'>
    <% if (ctx.response.results.length) { %>
        <div class='pool-list-controls'>
            <span class='view-toggle'>
                <a href data-view='grid' class='<%- ctx.settings.poolsView === 'table' ? '' : 'active' %>'>Grid</a>
                <a href data-view='table' class='<%- ctx.settings.poolsView === 'table' ? 'active' : '' %>'>Table</a>
            </span>
        </div>

        <% if (ctx.settings.poolsView === 'table') { %>
            <div class='table-wrap'>
                <table>
                    <thead>
                        <th class='names'>
                            <% if (ctx.parameters.query == 'sort:name' || !ctx.parameters.query) { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: '-sort:name'}) %>'>Pool name(s)</a>
                            <% } else { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: 'sort:name'}) %>'>Pool name(s)</a>
                            <% } %>
                        </th>
                        <th class='post-count'>
                            <% if (ctx.parameters.query == 'sort:post-count') { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: '-sort:post-count'}) %>'>Post count</a>
                            <% } else { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: 'sort:post-count'}) %>'>Post count</a>
                            <% } %>
                        </th>
                        <th class='creation-time'>
                            <% if (ctx.parameters.query == 'sort:creation-time') { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: '-sort:creation-time'}) %>'>Created on</a>
                            <% } else { %>
                                <a href='<%- ctx.formatClientLink('pools', {query: 'sort:creation-time'}) %>'>Created on</a>
                            <% } %>
                        </th>
                        <th class='read'>Read</th>
                    </thead>
                    <tbody>
                        <% for (let pool of ctx.response.results) { %>
                            <tr>
                                <td class='names'>
                                    <ul>
                                        <% for (let name of pool.names) { %>
                                            <li><%= ctx.makePoolLink(pool.id, false, false, pool, name) %></li>
                                        <% } %>
                                    </ul>
                                </td>
                                <td class='post-count'>
                                    <a href='<%- ctx.formatClientLink('posts', {query: 'pool:' + pool.id}) %>'><%- pool.postCount %></a>
                                </td>
                                <td class='creation-time'>
                                    <%= ctx.makeRelativeTime(pool.creationTime) %>
                                </td>
                                <td class='read'>
                                    <a href='<%- ctx.formatClientLink('pool', pool.id, 'read') %>'>Read</a>
                                </td>
                            </tr>
                        <% } %>
                    </tbody>
                </table>
            </div>
        <% } else { %>
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
                            <% if (pool.category && pool.category !== 'default') { %>
                                <span class='cover-badge <%- ctx.makeCssName(pool.category, 'pool') %>'><%- pool.category %></span>
                            <% } %>
                        </a>
                        <a class='title' href='<%- pool.postCount ? ctx.formatClientLink('pool', pool.id, 'read') : ctx.formatClientLink('pool', pool.id) %>'><%- pool.names[0] %></a>
                    </li>
                <% } %>
            </ul>
        <% } %>
    <% } else { %>
        <p class='no-pools'>No pools found.</p>
    <% } %>
</div>
