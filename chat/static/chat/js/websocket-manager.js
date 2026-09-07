/**
 * @file
 * Shared WebSocket connection manager.
 * Provides a singleton WebSocket instance that can be used by multiple modules.
 * Handles connection lifecycle, message routing, and async request/response patterns.
 *
 * Konsumenci:
 *  - pełny czat (chat.js przez wsapi.js),
 *  - powiadomienia (notifications.js),
 *  - embedded chat (chat-embedded.js).
 *
 * API subskrypcyjne zamiast pojedynczych callbacków — żaden konsument
 * nie nadpisuje handlera innego konsumenta, a kolejność inicjalizacji
 * modułów nie wpływa na dostarczanie wiadomości ani zdarzeń połączenia.
 */

/** Timeout dla żądań sendJsonAsync — zabezpiecza przed „wiecznym" oczekiwaniem
 * na odpowiedź TRACE, gdy socket jest długo rozłączony lub serwer nie odpowiada. */
const REQUEST_TIMEOUT_MS = 15000;

let sharedWebSocketInstance = null;

/**
 * Get the singleton WebSocket manager instance
 * Creates connection if it doesn't exist yet
 * @returns {Object} WebSocket manager with methods for messaging and subscriptions
 */
export function getSharedWebSocket() {
    if (sharedWebSocketInstance === null) {
        sharedWebSocketInstance = createWebSocketManager();
    }
    return sharedWebSocketInstance;
}

/**
 * Creates a new WebSocket manager with connection and message handling
 * @private
 * @returns {Object} WebSocket manager object
 */
function createWebSocketManager() {
    let promises = {};
    const messageHandlers = new Set();
    const connectionSubscribers = new Set();
    let socketOpen = false;
    let everOpened = false;

    // Determine WebSocket URL based on current protocol
    let ws_scheme = window.location.protocol == "https:" ? "wss" : "ws";
    let ws_path = ws_scheme + '://' + window.location.host + "/chat/stream/";
    console.log("Connecting to " + ws_path);

    // Create WebSocket connection
    let socket = new ReconnectingWebSocket(ws_path);

    function notifySubscribers(method, event) {
        for (const sub of [...connectionSubscribers]) {
            try {
                sub[method]?.(event);
            } catch (err) {
                console.error("Error in connection subscriber:", err);
            }
        }
    }

    /**
     * Main message handler for all incoming WebSocket messages
     * Routes messages to appropriate handlers based on content
     * @param {Object} data - Parsed JSON message from server
     */
    socket.onmessage = (e) => {
        let data;
        try {
            data = JSON.parse(e.data);
        } catch (err) {
            console.error("Failed to parse WebSocket message:", err);
            return;
        }

        // Handle errors
        if (data.error) {
            console.error(data.error);
        }

        // Route TRACE_ID messages to async promise resolution/rejection
        if (data.__TRACE_ID) {
            if (data.error) {
                rejectAsync(data, promises);
            } else {
                receiveAsync(data, promises);
            }
            return;
        }

        // Non-TRACE messages go to ALL subscribers — błąd jednego handlera
        // nie może wyciszyć pozostałych konsumentów.
        for (const handler of [...messageHandlers]) {
            try {
                handler(data);
            } catch (err) {
                console.error("Error in message handler:", err);
            }
        }
    };

    socket.onopen = function() {
        //console.log("Connected to socket");
        const event = { reconnected: everOpened, alreadyOpen: false };
        socketOpen = true;
        everOpened = true;
        notifySubscribers('onOpen', event);
    };

    socket.onclose = function() {
        console.log("Disconnected from socket");
        socketOpen = false;
        // Nie odrzucamy oczekujących żądań: ReconnectingWebSocket kolejkuje
        // wysyłki na czas rozłączenia i wypycha je po ponownym open — timeout
        // w sendJsonAsync ogranicza realnie zawieszone requesty.
        notifySubscribers('onClose');
    };

    // Set up beforeunload handler to close socket
    window.addEventListener('beforeunload', () => {
        console.log("beforeunload: Closing connection " + ws_path);
        socket.close();
    });

    /**
     * Resolves a pending promise with async response data
     * @param {Object} obj - Response object with __TRACE_ID
     * @param {Object} promises - Promise registry
     */
    function receiveAsync(obj, promises) {
        let ID = obj.__TRACE_ID;
        if (promises[ID] === undefined) {
            console.warn("received __TRACE_ID of " + ID + " that does not exist locally");
            return;
        }
        promises[ID].resolve(obj);
        delete promises[ID];
    }

    /**
     * Rejects a pending promise with error data
     * @param {Object} obj - Error object with __TRACE_ID and error message
     * @param {Object} promises - Promise registry
     */
    function rejectAsync(obj, promises) {
        let ID = obj.__TRACE_ID;
        if (promises[ID] === undefined) {
            console.warn("received error __TRACE_ID of " + ID + " that does not exist locally:", obj.error);
            return;
        }
        promises[ID].reject(obj.error);
        delete promises[ID];
    }

    return {
        /**
         * Raw WebSocket instance (use with caution)
         */
        socket: socket,

        /**
         * Subskrybuje wszystkie wiadomości bez __TRACE_ID.
         * Wielu subskrybentów jest obsługiwanych; każdy dostaje każdą wiadomość.
         * @param {Function} handler - Function to call with message data
         * @returns {Function} unsubscribe
         */
        subscribeMessages: function(handler) {
            messageHandlers.add(handler);
            return () => messageHandlers.delete(handler);
        },

        /**
         * Subskrybuje zdarzenia cyklu życia połączenia.
         * onOpen dostaje { reconnected, alreadyOpen }: reconnected=true przy
         * kolejnym otwarciu po zerwaniu; alreadyOpen=true gdy subskrypcja
         * zarejestrowała się po otwarciu socketu (wywołanie asynchroniczne).
         * @param {{onOpen?: Function, onClose?: Function}} subscriber
         * @returns {Function} unsubscribe
         */
        subscribeConnection: function(subscriber) {
            connectionSubscribers.add(subscriber);
            if (socketOpen && subscriber.onOpen) {
                queueMicrotask(() => {
                    if (connectionSubscribers.has(subscriber)) {
                        try {
                            subscriber.onOpen({ reconnected: false, alreadyOpen: true });
                        } catch (err) {
                            console.error("Error in connection subscriber:", err);
                        }
                    }
                });
            }
            return () => connectionSubscribers.delete(subscriber);
        },

        /**
         * Czy socket jest aktualnie otwarty.
         * @returns {boolean}
         */
        isOpen: function() {
            return socket.readyState === WebSocket.OPEN;
        },

        /**
         * Send a JSON message over WebSocket (no response expected)
         * @param {Object} obj - Object to send (will be JSON stringified)
         */
        sendJson: function(obj) {
            socket.send(JSON.stringify(obj));
        },

        /**
         * Send a JSON message and wait for response
         * Uses __TRACE_ID to correlate request/response
         * @param {Object} obj - Object to send
         * @param {Object} [options]
         * @param {number} [options.timeout] - ms; domyślnie REQUEST_TIMEOUT_MS.
         *        Po upływie promise odrzuca 'REQUEST_TIMEOUT'.
         * @returns {Promise<Object>} - Promise resolving to server response
         */
        sendJsonAsync: function(obj, { timeout = REQUEST_TIMEOUT_MS } = {}) {
            let ID = Math.floor(Math.random() * 1000000) + 1;
            obj.__TRACE_ID = ID;

            let promise = new Promise(
                (resolve, reject) => {
                    const timer = setTimeout(() => {
                        if (promises[ID] !== undefined) {
                            delete promises[ID];
                            reject('REQUEST_TIMEOUT');
                        }
                    }, timeout);
                    promises[ID] = {
                        resolve: (value) => { clearTimeout(timer); resolve(value); },
                        reject: (error) => { clearTimeout(timer); reject(error); }
                    }
                }
            );

            this.sendJson(obj);
            return promise;
        }
    };
}
