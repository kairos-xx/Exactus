import assert from "node:assert/strict";
import test from "node:test";
/**
 * Immutable metadata associated with a browser page lifecycle event.
 *
 * @typedef {Readonly<{
 *   identity: number,
 *   title: string,
 *   url: string,
 * }>} PageMetadata
 */
/**
 * Native browser process metadata associated with a lifecycle event.
 *
 * @typedef {Readonly<{
 *   pid?: number,
 *   exitCode?: number,
 * }>} ProcessMetadata
 */
/**
 * Lifecycle event target used to exercise browser lifecycle subscriptions.
 *
 * The target provides a small typed abstraction over `EventTarget` so tests
 * can emit lifecycle events without depending on browser example JavaScript,
 * HTML, or a real browser process.
 *
 * @extends {EventTarget}
 */
class LifecycleTarget extends EventTarget {
	/**
	 * Emit a lifecycle event with immutable event metadata.
	 *
	 * @param {string} type Lifecycle event type.
	 * @param {PageMetadata | ProcessMetadata} detail Event metadata.
	 * @returns {boolean} Whether the event was not canceled.
	 */
	emit(type, detail) {
		return this.dispatchEvent(new CustomEvent(type, {
			detail,
		}), );
	}
}
/**
 * Verify that page-close events retain their independent metadata snapshot.
 *
 * @returns {void}
 */
const testCloseMetadata = () => {
	const target = new LifecycleTarget();
	/** @type {PageMetadata[]} */
	const events = [];
	/** @type {PageMetadata} */
	const page = Object.freeze({
		identity: 17,
		title: "Example",
		url: "https://example.com/final",
	});
	target.addEventListener("pageclose", event => {
		/** @type {CustomEvent<PageMetadata>} */
		const lifecycleEvent = /** @type {CustomEvent<PageMetadata>} */ (event);
		events.push(lifecycleEvent.detail);
	});
	assert.equal(target.emit("pageclose", page), true);
	assert.deepEqual(events, [page]);
};
/**
 * Verify that multiple lifecycle listeners execute in registration order.
 *
 * @returns {void}
 */
const testListenerOrder = () => {
	const target = new LifecycleTarget();
	/** @type {string[]} */
	const calls = [];
	target.addEventListener("disconnect", () => {
		calls.push("first");
	});
	target.addEventListener("disconnect", () => {
		calls.push("second");
	});
	assert.equal(target.emit("disconnect", {
		pid: 42,
	}), true, );
	assert.deepEqual(calls, ["first", "second"]);
};
/**
 * Verify that removed lifecycle listeners receive no subsequent events.
 *
 * @returns {void}
 */
const testListenerRemoval = () => {
	const target = new LifecycleTarget();
	/** @type {string[]} */
	const calls = [];
	/**
	 * Record invocation of the removable listener.
	 *
	 * @returns {void}
	 */
	const callback = () => {
		calls.push("called");
	};
	target.addEventListener("processexit", callback);
	target.removeEventListener("processexit", callback);
	assert.equal(target.emit("processexit", {
		exitCode: 0,
	}), true, );
	assert.deepEqual(calls, []);
};
test("browser lifecycle events carry independent close metadata", testCloseMetadata, );
test("multiple lifecycle listeners receive the same event in order", testListenerOrder, );
test("removed lifecycle listeners are not called", testListenerRemoval);
