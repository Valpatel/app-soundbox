// Standalone widget: real click handler/core vote, delayed network, no second skip.
const assert = require('node:assert/strict');
const {RadioWidgetCore} = require('../static/js/radio-widget-core.js');
const {RadioWidgetInstance} = require('../static/js/radio-widget.js');
global.window = {};
global.document = {addEventListener() {}};
(async () => {
    const core = Object.create(RadioWidgetCore.prototype);
    const old = {id: 'old'}, next = {id: 'next', downvotes: 0};
    let skips = 0, pauses = 0, resolveVote, submitted, submittedUrl;
    Object.assign(core, {currentTrack: old, queue: [old, next], userId: 'tester',
        apiBaseUrl: '', currentVote: 0, audioElement: {pause() {pauses++;}},
        _events: {emit(name) {assert.notEqual(name, 'vote', 'Old vote must not repaint next track');}},
        next() {skips++; this.currentTrack = this.queue.shift();}});
    global.fetch = (url, request) => {
        submitted = JSON.parse(request.body);
        submittedUrl = url;
        return new Promise(resolve => {resolveVote = resolve;});
    };
    let click;
    const button = {classList: {contains() {return false;}}, addEventListener(_, fn) {click=fn;}};
    const widget = Object.create(RadioWidgetInstance.prototype);
    widget.core = core;
    widget.container = {querySelectorAll(selector) {return selector === '[data-action="downvote"]' ? [button] : [];}, querySelector() {return null;}};
    widget._attachControlHandlers();
    click();
    assert.equal(skips, 1);
    assert.equal(pauses, 1);
    assert.equal(core.currentTrack, next);
    assert.equal(submittedUrl, '/api/library/old/vote');
    assert.equal(submitted.generation_id, 'old');
    assert.equal(submitted.vote, -1);
    resolveVote({ok: true, json: async () => ({downvotes: 99, upvotes: 0})});
    await new Promise(resolve => setTimeout(resolve, 1200));
    assert.equal(skips, 1);
    assert.equal(core.currentTrack.downvotes, 0);
    assert.equal(core.currentVote, 0);
    console.log('Standalone widget: immediate single skip and delayed vote identity passed');
})().catch(error => {console.error(error); process.exitCode=1;});
