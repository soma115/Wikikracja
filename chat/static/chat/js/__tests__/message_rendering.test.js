const fs = require('fs');
const path = require('path');

const source = fs.readFileSync(path.join(__dirname, '..', 'chat.js'), 'utf8');
const helperSource = source.match(/function isRealtimeMessage\([\s\S]*?\n}\n/)[0];
const isRealtimeMessage = new Function(`${helperSource}; return isRealtimeMessage;`)();

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
