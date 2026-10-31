import assert from "node:assert/strict";
import test from "node:test";
import {
	Router,
} from "../../../../packages/exactus_mcp/bridge/worker.js";
/** Origin used by every request in this suite. */
const ORIGIN = "https://worker.example";
/** Canonical protected-resource URL for the suite origin. */
const RESOURCE = `${ORIGIN}/mcp`;
/**
 * Options the Worker's KV ``put`` accepts.
 *
 * @typedef {object} KVPutOptions
 * @property {number} [expirationTtl] Expiration in seconds.
 */
/**
 * Create an in-memory stand-in for the Worker KV binding.
 *
 * @returns {{store: Map<string, string>,
 *   get: (key: string) => Promise<string | null>,
 *   put: (key: string, value: string, options?: KVPutOptions) =>
 *   Promise<void>,
 *   delete: (key: string) => Promise<void>,
 *   puts: {key: string, options: KVPutOptions | undefined}[]}}
 *   Fake KV namespace.
 */
const fakeKV = () => {
	/** @type {Map<string, string>} */
	const store = new Map();
	/** @type {{key: string, options: KVPutOptions | undefined}[]} */
	const puts = [];
	return {
		store,
		puts,
		get: async (/** @type {string} */ key) => store.get(key) ?? null,
		put: async (
			/** @type {string} */ key,
			/** @type {string} */ value,
			/** @type {KVPutOptions | undefined} */ options,
		) => {
			store.set(key, value);
			puts.push({key, options});
		},
		delete: async (/** @type {string} */ key) => {
			store.delete(key);
		},
	};
};
/**
 * Build a Worker environment binding object.
 *
 * @returns {{ROUTING: ReturnType<typeof fakeKV>,
 *   CONTROL_SECRET: string, OAUTH_LOGIN_SECRET: string}} Bindings.
 */
const fakeEnv = () => ({
	ROUTING: fakeKV(),
	CONTROL_SECRET: "control-secret",
	OAUTH_LOGIN_SECRET: "login-secret",
});
/**
 * Build a request against the suite origin.
 *
 * @param {string} path Request path and query.
 * @param {RequestInit} [options] Request constructor options.
 * @returns {Request} Worker request.
 */
const req = (path, options = {}) => new Request(`${ORIGIN}${path}`, options);
/**
 * Replace ``globalThis.fetch`` and return a synchronous restore function.
 *
 * @param {typeof fetch} replacement Replacement implementation.
 * @returns {() => void} Restore the previous fetch.
 */
const captureFetch = replacement => {
	const original = globalThis.fetch;
	globalThis.fetch = replacement;
	return () => {
		globalThis.fetch = original;
	};
};
/**
 * Read a required key from the fake KV store.
 *
 * @param {ReturnType<typeof fakeKV>} kv Fake KV namespace.
 * @param {string} key Store key.
 * @returns {string} Stored value.
 */
const stored = (kv, key) => {
	const value = kv.store.get(key);
	assert.ok(value !== undefined, `missing KV value ${key}`);
	return value;
};
test("metadata endpoints describe the OAuth surface", async () => {
	const env = fakeEnv();
	const resource = await Router.fetch(
		req("/.well-known/oauth-protected-resource"),
		env,
	);
	assert.equal(resource.status, 200);
	const resourceBody = await resource.json();
	assert.equal(resourceBody.resource, RESOURCE);
	assert.deepEqual(resourceBody.authorization_servers, [ORIGIN]);
	const namespaced = await Router.fetch(
		req("/.well-known/oauth-protected-resource/mcp"),
		env,
	);
	assert.equal(namespaced.status, 200);
	const server = await Router.fetch(
		req("/.well-known/oauth-authorization-server"),
		env,
	);
	const serverBody = await server.json();
	assert.equal(serverBody.issuer, ORIGIN);
	assert.equal(serverBody.token_endpoint, `${ORIGIN}/oauth/token`);
	assert.deepEqual(serverBody.code_challenge_methods_supported, ["S256"]);
});
test("registerClient rejects wrong methods and metadata", async () => {
	const env = fakeEnv();
	const get = await Router.registerClient(req("/oauth/register"), env);
	assert.equal(get.status, 405);
	await Promise.all([
		{},
		{redirect_uris: "https://chatgpt.com/cb"},
		{redirect_uris: []},
		{redirect_uris: ["http://chatgpt.com/cb"]},
		{redirect_uris: ["https://example.com/cb"]},
		{redirect_uris: ["https://chatgpt.com/cb", 42]},
		{redirect_uris: ["not a url"]},
	].map(async body => {
		const response = await Router.registerClient(req("/oauth/register", {
			method: "POST",
			body: JSON.stringify(body),
		}), env);
		assert.equal(response.status, 400);
		assert.equal((await response.json()).error, "invalid_client_metadata");
	}));
});
test("registerClient stores a public client", async () => {
	const env = fakeEnv();
	const response = await Router.registerClient(req("/oauth/register", {
		method: "POST",
		body: JSON.stringify({
			redirect_uris: [
				"https://chatgpt.com/cb",
				"https://app.openai.com/cb",
			],
		}),
	}), env);
	assert.equal(response.status, 201);
	assert.equal(response.headers.get("Cache-Control"), "no-store");
	const body = await response.json();
	assert.match(body.client_id, /^client_/);
	assert.equal(body.token_endpoint_auth_method, "none");
	const client = JSON.parse(
		stored(env.ROUTING, `oauth:client:${body.client_id}`),
	);
	assert.deepEqual(client.redirect_uris, body.redirect_uris);
	return body.client_id;
});
test("authorize validates every required parameter", async () => {
	const env = fakeEnv();
	const base = {
		client_id: "client_x",
		redirect_uri: "https://chatgpt.com/cb",
		state: "s",
		code_challenge: "c",
		code_challenge_method: "S256",
		resource: RESOURCE,
	};
	await Promise.all(Object.keys(base).map(async omit => {
		const params = new URLSearchParams(base);
		params.delete(omit);
		const response = await Router.authorize(
			req(`/oauth/authorize?${params}`),
			env,
			new URL(`${ORIGIN}/oauth/authorize?${params}`),
		);
		assert.equal(response.status, 400, `missing ${omit}`);
	}));
	const wrongMethod = new URLSearchParams({
		...base,
		code_challenge_method: "plain",
	});
	const rejected = await Router.authorize(
		req(`/oauth/authorize?${wrongMethod}`),
		env,
		new URL(`${ORIGIN}/oauth/authorize?${wrongMethod}`),
	);
	assert.equal(rejected.status, 400);
	const foreign = new URLSearchParams({
		...base,
		resource: "https://other.example/mcp",
	});
	const foreignResponse = await Router.authorize(
		req(`/oauth/authorize?${foreign}`),
		env,
		new URL(`${ORIGIN}/oauth/authorize?${foreign}`),
	);
	assert.equal(foreignResponse.status, 400);
});
test("authorize rejects unknown and mismatched clients", async () => {
	const env = fakeEnv();
	env.ROUTING.store.set("oauth:client:client_known", JSON.stringify({
		redirect_uris: ["https://chatgpt.com/cb"],
	}));
	/**
	 * Run the authorize handler for a client/redirect pair.
	 *
	 * @param {string} client Client identifier.
	 * @param {string} redirect Redirect URI.
	 * @returns {Promise<Response>} Handler response.
	 */
	const authorize = async (client, redirect) => {
		const params = new URLSearchParams({
			client_id: client,
			redirect_uri: redirect,
			state: "s",
			code_challenge: "c",
			code_challenge_method: "S256",
			resource: RESOURCE,
		});
		return Router.authorize(
			req(`/oauth/authorize?${params}`),
			env,
			new URL(`${ORIGIN}/oauth/authorize?${params}`),
		);
	};
	assert.equal((await authorize("client_ghost", "https://chatgpt.com/cb")).status, 400);
	assert.equal((await authorize("client_known", "https://chatgpt.com/other")).status, 400);
});
/**
 * Register a client and collect its identifier.
 *
 * @param {ReturnType<typeof fakeEnv>} env Worker bindings.
 * @param {string} redirectUri Allowed callback.
 * @returns {Promise<string>} Issued client identifier.
 */
const register = async (env, redirectUri) => {
	const response = await Router.registerClient(req("/oauth/register", {
		method: "POST",
		body: JSON.stringify({redirect_uris: [redirectUri]}),
	}), env);
	assert.equal(response.status, 201);
	return (await response.json()).client_id;
};
test("GET authorize renders the escaped login form", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	const params = new URLSearchParams({
		client_id: clientId,
		redirect_uri: "https://chatgpt.com/cb",
		state: 'st"<>',
		code_challenge: "ch",
		code_challenge_method: "S256",
		resource: RESOURCE,
	});
	const response = await Router.authorize(
		req(`/oauth/authorize?${params}`),
		env,
		new URL(`${ORIGIN}/oauth/authorize?${params}`),
	);
	assert.equal(response.status, 200);
	const contentType = response.headers.get("Content-Type");
	assert.ok(contentType !== null);
	assert.match(contentType, /text\/html/);
	const html = await response.text();
	assert.match(html, /<form method="post">/);
	assert.match(html, /name="login_secret"/);
	assert.match(html, /value="st&quot;&lt;&gt;"/);
});
test("POST authorize requires the login secret", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	const body = new URLSearchParams({
		client_id: clientId,
		redirect_uri: "https://chatgpt.com/cb",
		state: "s",
		code_challenge: "c",
		code_challenge_method: "S256",
		resource: RESOURCE,
	});
	const response = await Router.authorize(
		req("/oauth/authorize", {method: "POST", body}),
		env,
		new URL(`${ORIGIN}/oauth/authorize`),
	);
	assert.equal(response.status, 401);
	const wrong = new URLSearchParams(body);
	wrong.set("login_secret", "wrong");
	const wrongResponse = await Router.authorize(
		req("/oauth/authorize", {method: "POST", body: wrong}),
		env,
		new URL(`${ORIGIN}/oauth/authorize`),
	);
	assert.equal(wrongResponse.status, 401);
});
/**
 * Complete an authorization POST and return the issued code.
 *
 * @param {ReturnType<typeof fakeEnv>} env Worker bindings.
 * @param {string} clientId Registered client identifier.
 * @param {string} challenge PKCE challenge to store.
 * @returns {Promise<string>} Authorization code.
 */
const grantCode = async (env, clientId, challenge) => {
	const body = new URLSearchParams({
		client_id: clientId,
		redirect_uri: "https://chatgpt.com/cb",
		state: "state-1",
		code_challenge: challenge,
		code_challenge_method: "S256",
		resource: RESOURCE,
		login_secret: env.OAUTH_LOGIN_SECRET,
	});
	const response = await Router.authorize(
		req("/oauth/authorize", {method: "POST", body}),
		env,
		new URL(`${ORIGIN}/oauth/authorize`),
	);
	assert.equal(response.status, 302);
	const location = response.headers.get("Location");
	assert.ok(location !== null, "authorize did not redirect");
	const callback = new URL(location);
	assert.equal(callback.origin, "https://chatgpt.com");
	assert.equal(callback.searchParams.get("state"), "state-1");
	assert.equal(callback.searchParams.get("iss"), ORIGIN);
	const code = callback.searchParams.get("code");
	assert.ok(code !== null, "redirect omitted the code");
	assert.ok(env.ROUTING.store.has(`oauth:code:${code}`));
	return code;
};
test("authorize issues a code and redirects with iss", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	await grantCode(env, clientId, "challenge-1");
	const entry = [...env.ROUTING.store.entries()].find(
		([key]) => key.startsWith("oauth:code:"),
	);
	assert.ok(entry !== undefined, "no oauth code stored");
	const record = JSON.parse(entry[1]);
	assert.equal(record.scope, "mcp:tools");
	const put = env.ROUTING.puts.find(
		({key}) => key.startsWith("oauth:code:"),
	);
	assert.ok(put !== undefined, "oauth code put not recorded");
	assert.equal(put.options?.expirationTtl, 300);
});
test("token enforces method, grant, and parameter shape", async () => {
	const env = fakeEnv();
	const get = await Router.token(req("/oauth/token"), env);
	assert.equal(get.status, 405);
	const badGrant = await Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({grant_type: "client_credentials"}),
	}), env);
	assert.equal((await badGrant.json()).error, "unsupported_grant_type");
	await Promise.all([
		new URLSearchParams({grant_type: "authorization_code"}),
		new URLSearchParams({grant_type: "authorization_code", code: "c"}),
	].map(async body => {
		const response = await Router.token(
			req("/oauth/token", {method: "POST", body}),
			env,
		);
		assert.equal((await response.json()).error, "invalid_grant");
	}));
	const unknown = await Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({
			grant_type: "authorization_code",
			code: "ghost",
			code_verifier: "v",
		}),
	}), env);
	assert.equal((await unknown.json()).error, "invalid_grant");
});
test("token rejects mismatched binding fields", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	const code = await grantCode(env, clientId, "challenge-1");
	/**
	 * Exchange the issued code with one overridden field.
	 *
	 * @param {Record<string, string>} overrides Field overrides.
	 * @returns {Promise<Response>} Token endpoint response.
	 */
	const exchange = async overrides => Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({
			grant_type: "authorization_code",
			code,
			code_verifier: "verifier-1",
			client_id: clientId,
			redirect_uri: "https://chatgpt.com/cb",
			resource: RESOURCE,
			...overrides,
		}),
	}), env);
	await Promise.all([
		{client_id: "client_other"},
		{redirect_uri: "https://chatgpt.com/other"},
		{resource: "https://other.example/mcp"},
	].map(async overrides => {
		const response = await exchange(overrides);
		assert.equal((await response.json()).error, "invalid_grant");
	}));
});
test("token issues a bearer token for a valid PKCE exchange", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	const verifier = "correct-horse-battery-staple";
	const challenge = await Router.pkceChallenge(verifier);
	const code = await grantCode(env, clientId, challenge);
	const response = await Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({
			grant_type: "authorization_code",
			code,
			code_verifier: verifier,
			client_id: clientId,
			redirect_uri: "https://chatgpt.com/cb",
			resource: RESOURCE,
		}),
	}), env);
	assert.equal(response.status, 200);
	assert.equal(response.headers.get("Cache-Control"), "no-store");
	const body = await response.json();
	assert.equal(body.token_type, "Bearer");
	assert.equal(body.expires_in, 3600);
	assert.equal(body.scope, "mcp:tools");
	assert.ok(!env.ROUTING.store.has(`oauth:code:${code}`));
	const hash = await Router.sha256(body.access_token);
	assert.ok(env.ROUTING.store.has(`oauth:token:${hash}`));
	const wrongVerifier = await grantCode(env, clientId, challenge);
	const rejected = await Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({
			grant_type: "authorization_code",
			code: wrongVerifier,
			code_verifier: "wrong-verifier",
			client_id: clientId,
			redirect_uri: "https://chatgpt.com/cb",
			resource: RESOURCE,
		}),
	}), env);
	assert.equal((await rejected.json()).error, "invalid_grant");
});
test("authorizedProxy challenges missing and unknown tokens", async () => {
	const env = fakeEnv();
	const anonymous = await Router.fetch(req("/mcp"), env);
	assert.equal(anonymous.status, 401);
	const authenticate = anonymous.headers.get("WWW-Authenticate");
	assert.ok(authenticate !== null);
	assert.match(authenticate, /resource_metadata="https:\/\/worker\.example\/\.well-known\/oauth-protected-resource"/);
	assert.match(authenticate, /scope="mcp:tools"/);
	const basic = await Router.fetch(req("/mcp", {
		headers: {Authorization: "Basic abc"},
	}), env);
	assert.equal(basic.status, 401);
	const unknown = await Router.fetch(req("/mcp", {
		headers: {Authorization: "Bearer ghost"},
	}), env);
	assert.equal(unknown.status, 401);
});
test("authorizedProxy enforces the token resource binding", async () => {
	const env = fakeEnv();
	const token = "bound-token";
	env.ROUTING.store.set(
		`oauth:token:${await Router.sha256(token)}`,
		JSON.stringify({
			resource: "https://other.example/mcp",
			scope: "mcp:tools",
		}),
	);
	const response = await Router.fetch(req("/mcp", {
		headers: {Authorization: `Bearer ${token}`},
	}), env);
	assert.equal(response.status, 401);
});
test("updateBackend enforces method, secret, and URL shape", async () => {
	const env = fakeEnv();
	const get = await Router.updateBackend(req("/_control/backend"), env);
	assert.equal(get.status, 405);
	const anonymous = await Router.updateBackend(req("/_control/backend", {
		method: "POST",
		body: JSON.stringify({url: "https://a.trycloudflare.com"}),
	}), env);
	assert.equal(anonymous.status, 401);
	/**
	 * Post one backend-control payload.
	 *
	 * @param {unknown} body JSON payload.
	 * @returns {Promise<Response>} Control response.
	 */
	const post = body => Router.updateBackend(req("/_control/backend", {
		method: "POST",
		headers: {Authorization: "Bearer control-secret"},
		body: JSON.stringify(body),
	}), env);
	await Promise.all([
		42,
		"not a url",
		"http://a.trycloudflare.com",
		"https://example.com",
		"https://u:p@a.trycloudflare.com",
		"https://a.trycloudflare.com/?q=1",
		"https://a.trycloudflare.com/#frag",
	].map(async url => {
		assert.equal((await post({url})).status, 400, String(url));
	}));
	assert.equal((await post({})).status, 400);
	const ok = await post({url: "https://a.trycloudflare.com/path/ignored"});
	assert.equal(ok.status, 200);
	assert.equal(env.ROUTING.store.get("current_backend_url"), "https://a.trycloudflare.com");
});
test("proxy reports missing backend and forwards when set", async () => {
	const env = fakeEnv();
	const unavailable = await Router.proxy(req("/anything"), env);
	assert.equal(unavailable.status, 503);
	env.ROUTING.store.set("current_backend_url", "https://b.trycloudflare.com");
	/** @type {Request | undefined} */
	let forwarded;
	const restore = captureFetch(
		async (/** @type {RequestInfo | URL} */ input) => {
			forwarded = input instanceof Request ? input : new Request(input);
			return new Response("backend-body", {
				status: 418,
				statusText: "Teapot",
				headers: {"X-Backend": "yes"},
			});
		},
	);
	try {
		const response = await Router.fetch(req("/some/path?x=1", {
			method: "POST",
			headers: {
				Host: "worker.example",
				Authorization: "Bearer strip-me",
				"X-Keep": "kept",
			},
		}), env);
		assert.equal(response.status, 418);
		assert.equal(response.statusText, "Teapot");
		assert.equal(response.headers.get("X-Backend"), "yes");
		assert.equal(await response.text(), "backend-body");
	} finally {
		restore();
	}
	assert.ok(forwarded);
	const target = new URL(forwarded.url);
	assert.equal(target.origin, "https://b.trycloudflare.com");
	assert.equal(`${target.pathname}${target.search}`, "/some/path?x=1");
	assert.equal(forwarded.method, "POST");
	assert.equal(forwarded.headers.get("X-Exactus-Origin-Secret"), "control-secret");
	assert.equal(forwarded.headers.get("X-Keep"), "kept");
	assert.equal(forwarded.headers.get("authorization"), null);
	assert.equal(forwarded.headers.get("host"), null);
});
test("end-to-end OAuth flow authorizes an MCP request", async () => {
	const env = fakeEnv();
	const clientId = await register(env, "https://chatgpt.com/cb");
	const verifier = "end-to-end-verifier";
	const code = await grantCode(env, clientId, await Router.pkceChallenge(verifier));
	const tokenResponse = await Router.token(req("/oauth/token", {
		method: "POST",
		body: new URLSearchParams({
			grant_type: "authorization_code",
			code,
			code_verifier: verifier,
			client_id: clientId,
			redirect_uri: "https://chatgpt.com/cb",
			resource: RESOURCE,
		}),
	}), env);
	const {access_token} = await tokenResponse.json();
	env.ROUTING.store.set("current_backend_url", "https://c.trycloudflare.com");
	const restore = captureFetch(async () => new Response("mcp-reply"));
	try {
		const response = await Router.fetch(req("/mcp", {
			headers: {Authorization: `Bearer ${access_token}`},
		}), env);
		assert.equal(response.status, 200);
		assert.equal(await response.text(), "mcp-reply");
	} finally {
		restore();
	}
});
