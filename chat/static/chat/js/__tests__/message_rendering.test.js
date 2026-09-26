const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(path.join(__dirname, '..', 'chat.js'), 'utf8');
const helperSource = source.match(/function ownMessagePresence\([\s\S]*?\n}\n/)[0];
const ownMessagePresence = new Function(`${helperSource}; return ownMessagePresence;`)();
const avatarHelperSource = source.match(/function ownMessageAvatar\([\s\S]*?\n}\n/)[0];
const ownMessageAvatar = new Function(`${avatarHelperSource}; return ownMessageAvatar;`)();
const realtimeHelperSource = source.match(/function isRealtimeMessage\([\s\S]*?\n}\n/)[0];
const isRealtimeMessage = new Function(`${realtimeHelperSource}; return isRealtimeMessage;`)();

test('marks a non-anonymous optimistic message as online with a parseable timestamp', () => {
    const presence = ownMessagePresence(false, 0);
    expect(presence.status).toBe('green');
    expect(presence.source).toBe('app');
    expect(Date.parse(presence.timestamp)).toBe(0);
});

test('keeps anonymous optimistic messages red', () => {
    expect(ownMessagePresence(true, 0)).toEqual({ status: 'red', source: '', timestamp: null });
});

test('uses the current user avatar for non-anonymous optimistic messages', () => {
    expect(ownMessageAvatar(false, { dataset: { avatar: '/media/avatar.png' } })).toBe('/media/avatar.png');
});

test('does not expose the current user avatar for anonymous messages', () => {
    expect(ownMessageAvatar(true, { dataset: { avatar: '/media/avatar.png' } })).toBeNull();
});

test('treats the sender echo with temp_id as a realtime message', () => {
    expect(isRealtimeMessage([{ new: false, temp_id: 'tmp-1' }])).toBe(true);
});

test('does not treat a one-message history response as realtime', () => {
    expect(isRealtimeMessage([{ new: false, temp_id: null }])).toBe(false);
});

test('treats a new message without an optimistic id as realtime', () => {
    expect(isRealtimeMessage([{ new: true, temp_id: null }])).toBe(true);
});

test('does not treat a batch as realtime', () => {
    expect(isRealtimeMessage([{ new: true }, { new: true }])).toBe(false);
});
