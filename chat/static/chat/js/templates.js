/**
 * @file
 * EJS template definitions for chat UI components.
 * Contains template literals for room layout, message display, and history modal.
 * Templates are compiled using EJS (Embedded JavaScript Templates).
 */

import { _ } from './utility.js';

/**
 * Room template - main chat room layout
 * Contains message container, image preview, and input controls
 * @type {string}
 */
const room_template = `
<div id='room'>

  <div class="tw-chat-breadcrumb-row">
    <div class="tw-chat-breadcrumb" id="chat-breadcrumb" role="button" tabindex="0" aria-label="${_("Show room list")}" aria-expanded="false" aria-controls="room-list"></div>
    <div class="tw-chat-sort-toolbar" id="chat-sort-toolbar" role="toolbar" aria-label="${_("Sorting and filter")}">
      <button type="button" class="tw-sort-btn tw-active" id="chat-sort-date" data-sort="date" data-order="desc">
        <i class="fas fa-clock fa-fw"></i>
        <span>${_("Date")}</span>
        <i class="fas fa-arrow-down tw-sort-arrow"></i>
      </button>
      <button type="button" class="tw-sort-btn" id="chat-sort-likes" data-sort="likes" data-order="desc">
        <i class="fas fa-thumbs-up fa-fw"></i>
        <span>${_("Likes")}</span>
        <i class="fas fa-arrow-down tw-sort-arrow tw-invisible"></i>
      </button>
      <button type="button" class="tw-sort-btn" id="chat-filter-popular" data-filter="popular">
        <i class="fas fa-fire fa-fw"></i>
        <span>${_("Popular")}</span>
      </button>
    </div>
  </div>

  <div class='tw-chat-messages'>
    <div class='tw-empty-chat-message'>
      ${_("This room is empty, be the first one to write something.")}
    </div>
  </div>

  <div class='tw-image-preview-container tw-d-none'>
    <div class='tw-preview-images'></div>
    <div class='tw-delete-images-preview'>
      <i class='fas fa-times'></i>
    </div>
  </div>

  <div class='tw-chat-controls'>
    <div class="tw-reply-preview tw-d-none" id="reply-preview">
      <span class="tw-reply-preview-label">↩ </span>
      <span class="tw-reply-preview-text" id="reply-preview-text"></span>
      <button class="tw-reply-preview-close" id="reply-preview-close" type="button" title="Anuluj odpowiedź">✕</button>
    </div>
    <div class="tw-compose-box">
      <!-- Rich text input -->
      <div id="message-input" class="tw-message-input-rich" contenteditable="true"
           role="textbox" aria-multiline="true" aria-label="${_("Reply to the appropriate message...")}"
           data-placeholder="${_("Reply to the appropriate message...")}"
           data-hint="${_("Enter send · Shift/Ctrl+Enter new line · Ctrl+B bold · Ctrl+I italic")}"></div>

      <!-- Bottom bar: tools left, counter+send right -->
      <div class="tw-compose-bar">
        <div class="tw-compose-bar-left">
          <!-- Image upload button -->
          <input type='file' id='file-input' class='tw-file-input' multiple='multiple'/>
          <label class='tw-fmt-btn' for='file-input' title='${_("Attach image")}'>
            <i class='fas fa-image'></i>
          </label>

          <div class="tw-compose-separator"></div>

          <div class="tw-fmt-toolbar" id="fmt-toolbar">
            <button class="tw-fmt-btn" data-cmd="bold"      title="Ctrl+B"><b>B</b></button>
            <button class="tw-fmt-btn" data-cmd="italic"    title="Ctrl+I"><i>I</i></button>
            <button class="tw-fmt-btn" data-cmd="underline" title="Ctrl+U"><u>U</u></button>
          </div>

          <!-- Anonymous toggle button -->
          <% if (is_public) { %>
            <div class="tw-compose-separator"></div>
            <button class='tw-fmt-btn tw-anonymous-toggle' id='anonymous-toggle' type='button' title='${_("Anonymous")}'>
              <i class='fas fa-user-secret'></i>
            </button>
          <% } %>
        </div>

        <div class="tw-compose-bar-right">
          <div class="tw-msg-counter" id="msg-counter">
            <span id="msg-counter-val"><%- messageMaxLength %></span> / <%- messageMaxLength %>
          </div>
          <button class='tw-send-message tw-btn tw-btn-primary tw-compose-send'>
            <i class='fas fa-paper-plane'></i>
          </button>
        </div>
      </div>
    </div>
  </div>
</div>
`;

/**
 * Message template - individual message display
 * Shows username, timestamp, content, attachments, and voting controls
 * @type {string}
 */
const message_template = `
<div class='tw-chat-message <% if (own) { %> tw-chat-message--own <% } %>' data-message-id="<%-message_id%>" data-room-id="<%-room_id%>">
  <div class='tw-chat-message-content'>

    <div class='tw-msg-body'>
      <% if (reply_to) { %>
      <div class="tw-msg-quote" data-reply-id="<%-reply_to.id%>" data-target-id="<%-reply_to.id%>" role="button" title="Przejdź do oryginału">
        <span class="tw-msg-quote-mark">"</span>
        <span class="tw-msg-quote-author">@<%- reply_to.display_name || reply_to.username %>:</span>
        <span class="tw-msg-quote-text"><%-reply_to.text_snippet%></span>
        <span class="tw-msg-quote-mark">"</span>
        <button class="tw-msg-quote-jump" data-target-id="<%-reply_to.id%>" type="button" title="Przejdź do oryginału">↗</button>
      </div>
      <% } %>
      <div class='tw-attachment-image-container'>
        <% if (attachments && attachments.images) { %>
          <% for (let filename of attachments.images) { %>
            <img class='tw-attached-image' loading='lazy' src='/media/uploads/<%- encodeURIComponent(filename).replace(/'/g, '%27') %>'>
          <% } %>
        <% } %>
      </div>
      <div class='tw-msg-text' data-raw="<%=raw_message%>"><%-message%></div>
    </div>

    <div class='tw-chat-message-header'>
      <div class='tw-chat-message-header-left'>
        <% const _hasProfileLink = (typeof user_id !== 'undefined' && user_id); %>
        <% if (_hasProfileLink) { %><a class='tw-username tw-username-link' href='/obywatele/<%- user_id %>/'><% } else { %><span class='tw-username'><% } %>
          <% if (typeof avatar_url !== 'undefined' && avatar_url) { %>
            <img class='tw-avatar tw-avatar-2xl' src='<%- avatar_url %>' alt=''>
          <% } else { %>
            <span class='tw-avatar tw-avatar-2xl tw-avatar-fallback<% if (typeof citizen_color_class !== "undefined" && citizen_color_class) { %> <%- citizen_color_class %><% } %>'><%= (typeof initials !== 'undefined' && initials) ? initials : (username || '').slice(0, 2).toUpperCase() %></span>
          <% } %><%= (typeof display_name !== 'undefined' && display_name) ? display_name : (username || '') %>
        <% if (_hasProfileLink) { %></a><% } else { %></span><% } %>
      </div>
      <div class='tw-chat-message-header-right'>
        <span class='tw-message-timestamp' data-message-id='<%-message_id%>'><%- latest_ts %></span>
        <button type='button' class='tw-btn tw-btn-sm tw-message-btn tw-show-history <% if (!edited) { %>tw-d-none<% } %>'
          data-message-id='<%-message_id%>'
          title='${_("edited")}'>
          <i class='fas fa-history'></i>
        </button>
        <% if (own) { %>
          <button type='button' class='tw-btn tw-btn-sm tw-message-btn tw-edit-message' data-message-id="<%-message_id%>"
            title='${_("edit")}'>
            <i class='fas fa-pen'></i>
          </button>
        <% } %>
        <button type='button'
          class='tw-btn tw-btn-sm tw-message-btn tw-reply-btn'
          data-message-id='<%-message_id%>'
          data-username='<%= (typeof display_name !== "undefined" && display_name) ? display_name : (username || "") %>'
          data-snippet='<%-raw_message.replace(/<[^>]*>/g,"").slice(0,320)%>'
          title='Odpowiedz'>
          <i class='fas fa-reply'></i>
        </button>
        <button type='button'
          class='tw-btn tw-btn-sm tw-message-btn tw-copy-message-url'
          data-room-id='<%-room_id%>'
          data-message-id='<%-message_id%>'
          title='${_("Copy link")}'>
          <i class='fas fa-link'></i>
        </button>
      </div>
    </div>

    <%
      const _totalVotes = upvotes + downvotes;
      const _pct = _totalVotes > 0 ? Math.round((upvotes / _totalVotes) * 100) : 0;
      const _barCls = _pct >= 60 ? 'tw-vote-bar--positive' : (_pct >= 40 ? 'tw-vote-bar--neutral' : 'tw-vote-bar--negative');
    %>
    <div class="tw-msg-meta-row">
      <% if (type == "public") { %>
        <button type='button' data-event-name='upvote' data-message-id="<%-message_id%>" class='tw-btn tw-btn-sm tw-message-btn tw-msg-vote' title='${_("Upvote")}<% if (typeof upvoters !== "undefined" && upvoters && upvoters.length) { %>: <%= upvoters.join(", ") %><% } %>'>
          <i class='fas fa-thumbs-up'></i>
          <span class='tw-msg-upvotes'><%-upvotes%></span>
        </button>
        <button type='button' data-event-name='downvote' data-message-id="<%-message_id%>" class='tw-btn tw-btn-sm tw-message-btn tw-msg-vote' title='${_("Downvote")}<% if (typeof downvoters !== "undefined" && downvoters && downvoters.length) { %>: <%= downvoters.join(", ") %><% } %>'>
          <i class='fas fa-thumbs-down'></i>
          <span class='tw-msg-downvotes'><%-downvotes%></span>
        </button>
      <% } %>

      <% if (_totalVotes >= 3) { %>
        <div class="tw-vote-bar-wrap">
          <div class="tw-vote-bar-fill <%- _barCls %>" style="--vote-progress:<%- _pct %>%"></div>
        </div>
        <span class="tw-vote-bar-label"><%- _pct %>% popiera</span>
      <% } %>

      <span class="tw-msg-divider" aria-hidden="true"></span>

      <% for (const [_key, _emoji, _label] of [['bulb','💡','Ciekawe'],['question','❓','Mam pytanie']]) { %>
        <button class="tw-reaction-btn<% if ((your_reactions||[]).includes(_key)) { %> tw-reaction-btn--active<% } %>"
                data-reaction="<%- _key %>" data-message-id="<%- message_id %>"
                type="button" title="<%- _label %>">
          <%- _emoji %><% if ((reactions[_key]||0) > 0) { %><span class="tw-reaction-count"><%- reactions[_key] %></span><% } %>
        </button>
      <% } %>

      <button type="button" class="tw-reaction-btn tw-read-by-toggle" data-message-id="<%- message_id %>" title="<%- (read_by && read_by.length) ? read_by.length + ' osób przeczytało tę wiadomość' : 'Nikt jeszcze nie przeczytał' %>">
        <i class="fas fa-eye"></i>
        <% if (read_by && read_by.length) { %><span class="tw-read-by-count"><%- read_by.length %></span><% } %>
      </button>
      <div class="tw-read-by-dropdown tw-d-none" id="read-by-dropdown-<%- message_id %>">
        <div class="tw-read-by-list">
          <% if (read_by && read_by.length) { %>
            <% for (const _u of read_by) { %>
              <div class="tw-read-by-item">
                <% if (_u.avatar_url) { %>
                  <img class="tw-avatar tw-avatar-xl" src="<%- _u.avatar_url %>" alt="<%- _u.display_name || _u.username %>">
                <% } else { %>
                  <span class="tw-avatar tw-avatar-xl tw-avatar-fallback<% if (_u.citizen_color_class) { %> <%- _u.citizen_color_class %><% } %>"><%= _u.initials || (_u.username || '').slice(0, 2).toUpperCase() %></span>
                <% } %>
                <span class="tw-read-by-username"><%- _u.display_name || _u.username %></span>
              </div>
            <% } %>
          <% } else { %>
            <div class="tw-read-by-item tw-read-by-empty">Nikt jeszcze nie przeczytał</div>
          <% } %>
        </div>
      </div>
    </div>

  </div>
</div>
`;

/**
 * Message history template - table showing edit history
 * Displays timestamped table of message edits
 * @type {string}
 */
const history_template = `
<table class='tw-chat-history-table tw-w-full'>
<% for (let [i, entry] of Object.entries(history)) { %>
  <tr>
    <td class='tw-chat-history-index'><%- parseInt(i) + 1 %>.</td>
    <td> <%- entry.text %> </td>
    <td class='tw-chat-history-meta'>
      <%- entry.formattedTime %>
    </td>
  </tr>
<% } %>
</table>
`;

/**
 * Compiles room template into a render function
 * @returns {Function} - EJS template function
 */
export const Room = ejs.compile(room_template);

/**
 * Compiles message template into a render function
 * @returns {Function} - EJS template function
 */
export const Message = ejs.compile(message_template);

/**
 * Compiles history template into a render function
 * @returns {Function} - EJS template function
 */
export const MessageHistory = ejs.compile(history_template);