/** Verify authenticated Studio transport and interrupted command responses. */
import { setImmediate } from "node:timers";
import assert from "node:assert/strict";
import test from "node:test";
import { StudioTransport } from "../../../../tools/record/studio/web/transport.js";
/** Restore every patched global after a transport contract test.
 * @param {import("node:test").TestContext} t Test cleanup registry.
 * @param {(...args: any[]) => Promise<any>} fetch Stubbed fetch double.
 * @returns {void}
 */
const environment = (t, fetch) => {
  for (const [name, value] of Object.entries({
    fetch,
    location: {
      hash: "#token=secret",
      pathname: "/studio",
    },
    history: {
      replaceState: () => {},
    },
    document: {
      getElementById: () => ({
        textContent: "",
      }),
    },
    EventSource: class {
      /** @param {string} url */
      constructor(url) {
        this.url = url;
      }
    },
  })) {
    const descriptor = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, {
      configurable: true,
      writable: true,
      value,
    });
    t.after(() =>
      descriptor
        ? Object.defineProperty(globalThis, name, descriptor)
        : Reflect.deleteProperty(globalThis, name),
    );
  }
};
test("authorization, snapshot, events, and command responses", async t => {
  /** @type {any[]} */
  const calls = [];
  environment(
    t,
    async (/** @type {string} */ url, /** @type {any} */ options) => {
      calls.push([url, options]);
      return {
        ok: true,
        json: async () => ({
          ok: true,
          result: {},
        }),
      };
    },
  );
  const transport = new StudioTransport();
  const messages = [];
  transport.outbound.connect(message => messages.push(JSON.parse(message)));
  await transport.connect();
  assert.equal(calls[0][1].headers.Authorization, "Bearer secret");
  assert.match(calls[1][0], /^\/api\/snapshot\?client=/);
  const events = /** @type {any} */ (transport.events);
  events.onmessage({
    data: '{"event":"snapshot"}',
  });
  events.onerror();
  await transport.send('{"id":"cmd"}');
  assert.equal(calls[2][1].headers["X-Studio-Client"], transport.client);
  assert.equal(messages.length, 2);
  transport.postMessage('{"id":"posted"}');
  await new Promise(done => {
    setImmediate(done);
  });
  assert.equal(messages.length, 3);
});
test("authorization and snapshot failures are explicit", async t => {
  environment(t, async () => ({
    ok: false,
  }));
  await assert.rejects(new StudioTransport().connect(), /authorization failed/);
  location.hash = "";
  await assert.rejects(new StudioTransport().connect(), /session unavailable/);
});
test("interrupted commands retain their request identifier", async t => {
  environment(t, async () => {
    throw new Error("offline");
  });
  const transport = new StudioTransport();
  /** @type {any} */
  let reply;
  transport.outbound.connect((/** @type {any} */ message) => {
    reply = JSON.parse(message);
  });
  await transport.send('{"id":"retry"}');
  assert.equal(reply.id, "retry");
  assert.equal(reply.ok, false);
  assert.match(reply.error, /Reconnect/);
  await assert.rejects(transport.send("invalid"), SyntaxError);
});
