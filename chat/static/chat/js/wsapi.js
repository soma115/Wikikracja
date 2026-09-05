/**
 * @file
 * WebSocket API module for chat communication.
 * Provides a high-level interface for real-time chat operations
 * including sending messages, joining rooms, voting, and file uploads.
 */

import { getSharedWebSocket } from './websocket-manager.js';
import { uploadFiles } from './chat-core.js';

/**
 * WebSocket API class for managing chat WebSocket connection
 * Handles all server communication through WebSocket protocol
 * @class
 */
export default class WsApi {
    /**
     * Constructs a new WsApi instance
     * Sets up message handlers using shared WebSocket connection
     */
    constructor() {
        this.socketMessageHandler = null;
        this.wsOnConnect = null;
        this.wsOnDisconnect = null;

        // Get shared WebSocket manager instance
        let ws = getSharedWebSocket();

        // Set up this instance's message handler for non-TRACE messages
        ws.setSocketMessageHandler(function(data) {
            if (data.error) {
                window.showToast ? window.showToast(data.error) : console.error('WS error:', data.error);
                return;
            }
            if (this.socketMessageHandler) {
                this.socketMessageHandler(data);
            } else {
                console.warn("No socket message handler set");
            }
        }.bind(this));

        // Register open/close callbacks
        ws.setOnConnect(() => {
            if (this.wsOnConnect) {
                this.wsOnConnect();
            }
        });

        ws.setOnDisconnect(() => {
            console.log("Disconnected from chat socket");
            if (this.wsOnDisconnect) {
                this.wsOnDisconnect();
            }
        });

        // Store reference to shared socket
        this.ws = ws;
    }

    /**
     * Called when WebSocket connection is established
     * Override in subclass to add custom initialization
     */
    async wsOnConnect() {
    }

    /**
     * Called when WebSocket connection is closed
     * Override in subclass to handle disconnection
     */
    async wsOnDisconnect() {
    }

    /**
     * Sends a JSON message over WebSocket (no response expected)
     * @param {Object} obj - Object to send (will be JSON stringified)
     */
    sendJson(obj) {
        this.ws.sendJson(obj);
    }

    /**
     * Sends a JSON message and waits for response
     * Uses __TRACE_ID to correlate request/response
     * @param {Object} obj - Object to send
     * @returns {Promise<Object>} - Promise resolving to server response
     */
    async sendJsonAsync(obj) {
        return await this.ws.sendJsonAsync(obj);
    }

    /**
     * Checks whether the underlying WebSocket connection is currently open.
     * Useful for showing a "connecting..." indicator before commands that
     * would otherwise be queued until the connection opens.
     * @returns {boolean}
     */
    isConnected() {
        return this.ws.socket.readyState === WebSocket.OPEN;
    }

    /**
     * Joins a chat room
     * @param {number} room_id - ID of the room to join
     * @returns {Promise<Object>} - Room data from server
     */
    async joinRoom(room_id) {
        return await this.sendJsonAsync({
            command: "join",
            room_id: room_id
        });
    }

    /**
     * Notifies server that room has been seen
     * @param {number} room_id - ID of room that was viewed
     */
    seenRoom(room_id) {
        this.sendJson({
            command: "room-seen",
            room_id: room_id
        });
    }

    /**
     * Sends a chat message to the current room
     * @param {number} room_id - ID of the room
     * @param {string} message - Message text content
     * @param {boolean} is_anonymous - Whether to send as anonymous
     * @param {Object} attachments - Attachment data (images array)
     * @param {number|null} reply_to_id - Reply target message ID
     * @param {string|null} temp_id - Client-generated ID for optimistic UI matching
     */
    sendMessage(room_id, message, is_anonymous, attachments, reply_to_id = null, temp_id = null) {
        this.sendJson({
            command: "send",
            room_id,
            message,
            is_anonymous,
            attachments,
            ...(reply_to_id ? { reply_to_id } : {}),
            ...(temp_id ? { temp_id } : {}),
        });
    }

    /**
     * ZMIANA 4B — toggle emoji reaction on a message.
     */
    toggleReaction(reaction, message_id) {
        this.sendJson({ command: 'message-react', reaction, message_id });
    }

    markMessageRead(message_id) {
        this.sendJson({ command: 'message-mark-read', message_id });
    }

    markMessagesReadBulk(message_ids, room_id) {
        if (!message_ids.length) return;
        this.sendJson({ command: 'messages-mark-read-bulk', message_ids, room_id });
    }

    /**
     * Edits an existing message
     * @param {number} message_id - ID of message to edit
     * @param {string} message - New message text
     * @param {Object} attachments - New attachments (images array)
     * @param {Array<string>} removed_attachments - Filenames to remove
     * @param {string|null} original_message - Original message text for comparison
     */
    editMessage(message_id, message, attachments = {}, removed_attachments = [], original_message = null) {
        let payload = {
            command: "edit-message",
            message_id: message_id
        };

        // Only include new_message if it changed
        if (original_message === null || message !== original_message) {
            payload.new_message = message;
        }

        // Add attachments if provided
        if (attachments && Object.keys(attachments).length > 0) {
            payload.attachments = attachments;
        }

        // Add removed attachments if provided
        if (removed_attachments && removed_attachments.length > 0) {
            payload.removed_attachments = removed_attachments;
        }

        this.sendJson(payload);
    }

    /**
     * Adds an upvote or downvote to a message
     * @param {string} vote - Vote type ('upvote' or 'downvote')
     * @param {number} message_id - ID of message to vote on
     */
    addVote(vote, message_id) {
        this.sendJson({
            command: "message-add-vote",
            vote: vote,
            message_id: message_id
        });
    }

    /**
     * Removes a vote from a message
     * @param {string} vote - Vote type ('upvote' or 'downvote')
     * @param {number} message_id - ID of message to remove vote from
     */
    removeVote(vote, message_id) {
        this.sendJson({
            command: "message-remove-vote",
            vote: vote,
            message_id: message_id
        });
    }

    /**
     * Re-fetches messages with given sort/filter parameters (server-side).
     * @param {number} room_id
     * @param {string} sort_by - 'date' | 'likes'
     * @param {string} order - 'asc' | 'desc'
     * @param {boolean} popular_only
     */
    fetchMessages(room_id, sort_by = 'date', order = 'desc', popular_only = false) {
        this.sendJson({
            command: 'fetch-messages',
            room_id,
            sort_by,
            order,
            popular_only,
        });
    }

    /**
     * Leaves the current chat room
     * @param {number} room_id - ID of room to leave
     * @returns {Promise<Object>} - Server response
     */
    async leaveRoom(room_id) {
        return await this.sendJsonAsync({
            command: "leave",
            room_id: room_id
        });
    }

    /**
     * Requests list of online users
     * @returns {Promise<Object>} - Online users data
     */
    async getOnlineUsers() {
        return await this.sendJsonAsync({
            command: "get-online-users"
        });
    }

    /**
     * Fetches edit history for a message
     * @param {number} message_id - ID of message
     * @returns {Promise<Object>} - Message history data
     */
    async getMessageHistory(message_id) {
        return await this.sendJsonAsync({
            command: "get-message-history",
            message_id: message_id,
        });
    }

    /**
     * Requests notification data (rooms with notifications enabled)
     * @returns {Promise<Object>} - Notification settings data
     */
    async getNotificationData() {
        return await this.sendJsonAsync({
            command: 'get-notifications-data'
        });
    }

    /**
     * Uploads files to the server
     * @param {FileList} files - Files to upload
     * @returns {Promise<Object>} - Upload response with filenames
     */
    async uploadFiles(files) {
        return uploadFiles(files, 'upload/', { compress: false });
    }

    /**
     * Toggles push notifications for a room
     * @param {number} room_id - ID of the room
     * @param {boolean} enabled - Whether to enable notifications
     */
    toggleNotifications(room_id, enabled) {
        this.sendJson({
            command: 'toggle-notifications',
            room_id,
            enabled
        });
    }

    /**
     * Marks a room as unread/unseen
     * @param {number} room_id - ID of the room
     */
    markRoomUnseen(room_id) {
        this.sendJson({
            command: 'room-unseen',
            room_id
        });
    }
}
