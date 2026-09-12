import { getSharedWebSocket } from './websocket-manager.js';

const HEARTBEAT_INTERVAL_MS = 15 * 60 * 1000;
const ACTIVITY_THROTTLE_MS = 5 * 60 * 1000;

function formatPresenceTimestamp(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return '';
    const pad = (value) => String(value).padStart(2, '0');
    return `${pad(date.getDate())}.${pad(date.getMonth() + 1)}.${date.getFullYear()} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function relativePresenceTime(timestamp) {
    const date = new Date(timestamp || '');
    if (Number.isNaN(date.getTime())) return '';
    const seconds = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
    const labels = window.WK_PRESENCE_I18N || {};
    const interpolate = (label, value) => (label || '').replace('%s', String(value));
    if (seconds < 60) return labels.now || 'Active now';
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return interpolate(minutes === 1 ? labels.minuteOne : labels.minutes, minutes);
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return interpolate(hours === 1 ? labels.hourOne : labels.hours, hours);
    const dateLabel = formatPresenceTimestamp(timestamp);
    const yesterday = new Date(Date.now() - 24 * 60 * 60 * 1000);
    if (date.toDateString() === yesterday.toDateString()) return interpolate(labels.yesterday, dateLabel.slice(-5));
    const days = Math.floor(hours / 24);
    if (days < 7) return interpolate(labels.days, days);
    return interpolate(labels.onDate, dateLabel);
}

function initializePresence() {
    const websocket = getSharedWebSocket();
    let lastActivitySentAt = 0;
    const presencePopovers = new Map();

    const closePresencePopovers = (except = null) => {
        presencePopovers.forEach((popover, element) => {
            if (element !== except) popover.hide();
        });
    };

    const relativeTitle = (element) => {
        const relative = relativePresenceTime(element.dataset.presenceTimestamp);
        if (!relative) return element.getAttribute('title') || '';
        const current = element.getAttribute('title') || '';
        const separator = current.lastIndexOf(' / ');
        return separator >= 0 ? `${current.slice(0, separator)} / ${relative}` : relative;
    };

    const updatePresenceTitle = (element) => {
        const title = relativeTitle(element);
        if (!title) return;
        element.setAttribute('title', title);
        element.dataset.twTitle = title;
        const popover = presencePopovers.get(element);
        if (popover) popover.setContent({ '.tw-popover-header': title });
    };

    const initializePresencePopovers = () => {
        if (typeof window.TwPopover === 'undefined') return;
        document.querySelectorAll('[data-presence-user-id]').forEach((element) => {
            if (presencePopovers.has(element)) return;
            const initialTitle = relativeTitle(element) || `${element.dataset.presenceStatus || ''}: ${element.dataset.presenceSource || ''}: ${relativePresenceTime(element.dataset.presenceTimestamp)}`;
            element.setAttribute('title', initialTitle);
            element.dataset.twTitle = initialTitle;
            const popover = new window.TwPopover(element, { trigger: 'manual', placement: 'top', title: initialTitle });
            const toggle = (event) => {
                event.preventDefault();
                event.stopPropagation();
                closePresencePopovers(element);
                popover.toggle();
            };
            element.setAttribute('role', 'button');
            element.setAttribute('tabindex', '0');
            element.addEventListener('click', toggle);
            element.addEventListener('keydown', (event) => {
                if (event.key === 'Enter' || event.key === ' ') toggle(event);
            });
            presencePopovers.set(element, popover);
        });
    };

    document.addEventListener('click', () => closePresencePopovers());

    const sendActivity = () => {
        const now = Date.now();
        if (!websocket.isOpen() || now - lastActivitySentAt < ACTIVITY_THROTTLE_MS) return;
        lastActivitySentAt = now;
        websocket.sendJson({ command: 'presence-heartbeat' });
    };

    const refreshPresenceStatuses = () => {
        initializePresencePopovers();
        const now = Date.now();
        document.querySelectorAll('[data-presence-user-id]').forEach((element) => {
            const timestamp = Date.parse(element.dataset.presenceTimestamp || '');
            const greenMinutes = Number(element.dataset.presenceGreenMinutes);
            const yellowDays = Number(element.dataset.presenceYellowDays);
            let status = 'red';
            if (Number.isFinite(timestamp) && now - timestamp <= greenMinutes * 60 * 1000) {
                status = 'green';
            } else if (Number.isFinite(timestamp) && now - timestamp <= yellowDays * 24 * 60 * 60 * 1000) {
                status = 'yellow';
            }
            element.dataset.presenceStatus = status;
            element.classList.remove('tw-presence-green', 'tw-presence-yellow', 'tw-presence-red');
            element.classList.add(`tw-presence-${status}`);
            updatePresenceTitle(element);
        });
    };

    const handlePresenceMessage = (data) => {
        const presence = data.presence_update;
        if (!presence) return;
        document.querySelectorAll(`[data-presence-user-id="${presence.user_id}"]`).forEach((element) => {
            element.dataset.presenceStatus = presence.status;
            element.dataset.presenceSource = presence.source;
            element.dataset.presenceTimestamp = presence.timestamp || '';
            element.classList.remove('tw-presence-green', 'tw-presence-yellow', 'tw-presence-red');
            element.classList.add(`tw-presence-${presence.status}`);
            const title = `${presence.status}: ${presence.source}: ${relativePresenceTime(presence.timestamp)}`;
            element.setAttribute('title', title);
            element.dataset.twTitle = title;
            const popover = presencePopovers.get(element);
            if (popover) popover.setContent({ '.tw-popover-header': title });
        });
    };

    websocket.subscribeMessages((data) => {
        handlePresenceMessage(data);
        if (!data.presence_update) sendActivity();
    });
    websocket.subscribeConnection({ onOpen: sendActivity });
    window.addEventListener('click', sendActivity, { passive: true, capture: true });
    window.addEventListener('input', sendActivity, { passive: true, capture: true });
    window.setInterval(sendActivity, HEARTBEAT_INTERVAL_MS);
    window.setInterval(refreshPresenceStatuses, 60 * 1000);
    refreshPresenceStatuses();
}

window.wkOnReady(initializePresence);
