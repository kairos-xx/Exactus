const BACKEND_KEY = "current_backend_url";
const CONTROL_PATH = "/_control/backend";
const AUTHORIZATION_PATH = "/oauth/authorize";
const TOKEN_PATH = "/oauth/token";
const REGISTRATION_PATH = "/oauth/register";
const RESOURCE_METADATA_PATH = "/.well-known/oauth-protected-resource";
const AUTH_METADATA_PATH = "/.well-known/oauth-authorization-server";
const TOKEN_TTL_SECONDS = 3600;
const ORIGIN_SECRET_HEADER = "X-Exactus-Origin-Secret";
const CODE_TTL_SECONDS = 300;
/** @typedef {{get:(key:string)=>Promise<string|null>, put:(key:string, value:string, options?:{expirationTtl?:number})=>Promise<void>, delete:(key:string)=>Promise<void>}} RoutingKV */
/** @typedef {{ROUTING:RoutingKV, CONTROL_SECRET:string, OAUTH_LOGIN_SECRET:string}} WorkerEnv */
/** @typedef {{redirect_uris?:unknown}} RegistrationDocument */
/** @typedef {{url?:unknown}} BackendDocument */
/** Route OAuth, control, and MCP proxy requests. */
class Router {
	/** Dispatch one Worker request.
	 * @param {Request} request Incoming request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @returns {Promise<Response>} Routed response.
	 */
	static fetch = async (request, env) => {
		const url = new URL(request.url);
		if (url.pathname === CONTROL_PATH) return Router.updateBackend(request, env);
		if (url.pathname === RESOURCE_METADATA_PATH || url.pathname === `${RESOURCE_METADATA_PATH}/mcp`) return Router.resourceMetadata(url);
		if (url.pathname === AUTH_METADATA_PATH) return Router.authorizationMetadata(url);
		if (url.pathname === REGISTRATION_PATH) return Router.registerClient(request, env);
		if (url.pathname === AUTHORIZATION_PATH) return Router.authorize(request, env, url);
		if (url.pathname === TOKEN_PATH) return Router.token(request, env);
		if (url.pathname.startsWith("/mcp")) return Router.authorizedProxy(request, env, url);
		return Router.proxy(request, env);
	};
	/** Build the canonical protected-resource URL.
	 * @param {URL} url Request URL.
	 * @returns {string} MCP resource URL.
	 */
	static resource = url => `${url.origin}/mcp`;
	/** Return protected-resource metadata.
	 * @param {URL} url Request URL.
	 * @returns {Response} Metadata response.
	 */
	static resourceMetadata = url => Response.json({
		resource: Router.resource(url),
		authorization_servers: [url.origin],
		scopes_supported: ["mcp:tools"],
	});
	/** Return OAuth authorization-server metadata.
	 * @param {URL} url Request URL.
	 * @returns {Response} Metadata response.
	 */
	static authorizationMetadata = url => Response.json({
		issuer: url.origin,
		authorization_endpoint: `${url.origin}${AUTHORIZATION_PATH}`,
		token_endpoint: `${url.origin}${TOKEN_PATH}`,
		registration_endpoint: `${url.origin}${REGISTRATION_PATH}`,
		response_types_supported: ["code"],
		grant_types_supported: ["authorization_code"],
		code_challenge_methods_supported: ["S256"],
		token_endpoint_auth_methods_supported: ["none"],
		scopes_supported: ["mcp:tools"],
		authorization_response_iss_parameter_supported: true,
	});
	/** Register one public OAuth client.
	 * @param {Request} request Registration request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @returns {Promise<Response>} Registration response.
	 */
	static registerClient = async (request, env) => {
		if (request.method !== "POST") return new Response("Method Not Allowed", {
			status: 405
		});
		const body = /** @type {RegistrationDocument} */ (await request.json());
		if (!Array.isArray(body?.redirect_uris) || body.redirect_uris.length === 0 || !body.redirect_uris.every(Router.validRedirectUri)) return Response.json({
			error: "invalid_client_metadata"
		}, {
			status: 400
		});
		const clientId = `client_${crypto.randomUUID()}`;
		const client = {
			redirect_uris: body.redirect_uris,
			token_endpoint_auth_method: "none"
		};
		await env.ROUTING.put(`oauth:client:${clientId}`, JSON.stringify(client));
		return Response.json({
			client_id: clientId,
			client_id_issued_at: Math.floor(Date.now() / 1000),
			redirect_uris: client.redirect_uris,
			token_endpoint_auth_method: "none"
		}, {
			status: 201,
			headers: {
				"Cache-Control": "no-store"
			}
		});
	};
	/** Validate one dynamic-registration callback URL.
	 * @param {unknown} value Candidate URL.
	 * @returns {boolean} Whether the callback is trusted.
	 */
	static validRedirectUri = value => {
		if (typeof value !== "string") return false;
		try {
			const url = new URL(value);
			return url.protocol === "https:" && (url.hostname === "chatgpt.com" || url.hostname.endsWith(".openai.com"));
		} catch {
			return false;
		}
	};
	/** Authorize an OAuth client and issue a short-lived code.
	 * @param {Request} request Authorization request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @param {URL} url Request URL.
	 * @returns {Promise<Response>} Authorization response.
	 */
	static authorize = async (request, env, url) => {
		const params = request.method === "POST" ? new URLSearchParams(await request.text()) : url.searchParams;
		const clientId = params.get("client_id");
		const redirectUri = params.get("redirect_uri");
		const state = params.get("state");
		const challenge = params.get("code_challenge");
		const resource = params.get("resource");
		if (!clientId || !redirectUri || !state || !challenge || params.get("code_challenge_method") !== "S256" || resource !== Router.resource(url)) return new Response("Invalid OAuth request", {
			status: 400
		});
		const rawClient = await env.ROUTING.get(`oauth:client:${clientId}`);
		if (rawClient === null || !JSON.parse(rawClient).redirect_uris.includes(redirectUri)) return new Response("Invalid OAuth client", {
			status: 400
		});
		if (request.method === "GET") return Router.loginPage(params);
		if (params.get("login_secret") !== env.OAUTH_LOGIN_SECRET) return new Response("Unauthorized", {
			status: 401
		});
		const code = crypto.randomUUID();
		await env.ROUTING.put(`oauth:code:${code}`, JSON.stringify({
			client_id: clientId,
			redirect_uri: redirectUri,
			code_challenge: challenge,
			resource,
			scope: params.get("scope") || "mcp:tools"
		}), {
			expirationTtl: CODE_TTL_SECONDS
		});
		const callback = new URL(redirectUri);
		callback.searchParams.set("code", code);
		callback.searchParams.set("state", state);
		callback.searchParams.set("iss", url.origin);
		return Response.redirect(callback.toString(), 302);
	};
	/** Render the authorization login form.
	 * @param {URLSearchParams} params OAuth parameters.
	 * @returns {Response} HTML response.
	 */
	static loginPage = params => {
		const hidden = [...params.entries()].map(([key, value]) => `<input type="hidden" name="${Router.escape(key)}" value="${Router.escape(value)}">`).join("");
		return new Response(`<!doctype html><html><body><h1>Exactus MCP</h1><p>Authorize ChatGPT to use the local Exactus MCP server.</p><form method="post">${hidden}<label>Access secret <input type="password" name="login_secret" required autofocus></label><button type="submit">Authorize</button></form></body></html>`, {
			headers: {
				"Content-Type": "text/html; charset=utf-8",
				"Cache-Control": "no-store"
			}
		});
	};
	/** Escape text for an HTML attribute.
	 * @param {string} value Untrusted text.
	 * @returns {string} Escaped text.
	 */
	static escape = value => value.replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;");
	/** Exchange an authorization code for a bearer token.
	 * @param {Request} request Token request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @returns {Promise<Response>} Token response.
	 */
	static token = async (request, env) => {
		if (request.method !== "POST") return new Response("Method Not Allowed", {
			status: 405
		});
		const params = new URLSearchParams(await request.text());
		if (params.get("grant_type") !== "authorization_code") return Response.json({
			error: "unsupported_grant_type"
		}, {
			status: 400
		});
		const code = params.get("code");
		const verifier = params.get("code_verifier");
		if (!code || !verifier) return Response.json({
			error: "invalid_grant"
		}, {
			status: 400
		});
		const key = `oauth:code:${code}`;
		const raw = await env.ROUTING.get(key);
		if (raw === null) return Response.json({
			error: "invalid_grant"
		}, {
			status: 400
		});
		const data = JSON.parse(raw);
		if (data.client_id !== params.get("client_id") || data.redirect_uri !== params.get("redirect_uri") || data.resource !== params.get("resource") || await Router.pkceChallenge(verifier) !== data.code_challenge) return Response.json({
			error: "invalid_grant"
		}, {
			status: 400
		});
		await env.ROUTING.delete(key);
		const token = crypto.randomUUID() + crypto.randomUUID();
		await env.ROUTING.put(`oauth:token:${await Router.sha256(token)}`, JSON.stringify({
			resource: data.resource,
			scope: data.scope
		}), {
			expirationTtl: TOKEN_TTL_SECONDS
		});
		return Response.json({
			access_token: token,
			token_type: "Bearer",
			expires_in: TOKEN_TTL_SECONDS,
			scope: data.scope
		}, {
			headers: {
				"Cache-Control": "no-store"
			}
		});
	};
	/** Authenticate and proxy an MCP request.
	 * @param {Request} request MCP request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @param {URL} url Request URL.
	 * @returns {Promise<Response>} Proxy or challenge response.
	 */
	static authorizedProxy = async (request, env, url) => {
		const authorization = request.headers.get("Authorization") || "";
		const token = authorization.startsWith("Bearer ") ? authorization.slice(7) : "";
		const record = token ? await env.ROUTING.get(`oauth:token:${await Router.sha256(token)}`) : null;
		if (record === null) return new Response("Unauthorized", {
			status: 401,
			headers: {
				"WWW-Authenticate": `Bearer resource_metadata="${url.origin}${RESOURCE_METADATA_PATH}", scope="mcp:tools"`
			}
		});
		const data = JSON.parse(record);
		if (data.resource !== Router.resource(url)) return new Response("Unauthorized", {
			status: 401
		});
		return Router.proxy(request, env);
	};
	/** Hash text as lowercase hexadecimal SHA-256.
	 * @param {string} value Text to hash.
	 * @returns {Promise<string>} Hexadecimal digest.
	 */
	static sha256 = async value => {
		const bytes = new TextEncoder().encode(value);
		const digest = await crypto.subtle.digest("SHA-256", bytes);
		return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, "0")).join("");
	};
	/** Derive an OAuth S256 PKCE challenge.
	 * @param {string} verifier PKCE verifier.
	 * @returns {Promise<string>} Base64url challenge.
	 */
	static pkceChallenge = async verifier => {
		const bytes = new TextEncoder().encode(verifier);
		const digest = await crypto.subtle.digest("SHA-256", bytes);
		return btoa(String.fromCharCode(...new Uint8Array(digest))).replaceAll("+", "-").replaceAll("/", "_").replaceAll("=", "");
	};
	/** Publish the current ephemeral backend origin.
	 * @param {Request} request Control request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @returns {Promise<Response>} Update response.
	 */
	static updateBackend = async (request, env) => {
		if (request.method !== "POST") return new Response("Method Not Allowed", {
			status: 405
		});
		if (request.headers.get("Authorization") !== `Bearer ${env.CONTROL_SECRET}`) return new Response("Unauthorized", {
			status: 401
		});
		const payload = /** @type {BackendDocument} */ (await request.json());
		const backend = Router.validBackend(payload?.url);
		if (backend === null) return new Response("Invalid backend URL", {
			status: 400
		});
		await env.ROUTING.put(BACKEND_KEY, backend);
		return Response.json({
			backend,
			updated: true
		});
	};
	/** Normalize a trusted Quick Tunnel origin.
	 * @param {unknown} value Candidate URL.
	 * @returns {string|null} Normalized origin or null.
	 */
	static validBackend = value => {
		if (typeof value !== "string") return null;
		try {
			const url = new URL(value);
			if (url.protocol !== "https:" || !url.hostname.endsWith(".trycloudflare.com") || url.username !== "" || url.password !== "" || url.search !== "" || url.hash !== "") return null;
			return url.origin;
		} catch {
			return null;
		}
	};
	/** Forward one request to the published backend.
	 * @param {Request} request Incoming request.
	 * @param {WorkerEnv} env Worker bindings.
	 * @returns {Promise<Response>} Backend response.
	 */
	static proxy = async (request, env) => {
		const backend = await env.ROUTING.get(BACKEND_KEY);
		if (backend === null) return new Response("Backend unavailable", {
			status: 503
		});
		const incoming = new URL(request.url);
		const target = new URL(incoming.pathname + incoming.search, backend);
		const headers = new Headers(request.headers);
		headers.delete("host");
		headers.delete("authorization");
		headers.set(ORIGIN_SECRET_HEADER, env.CONTROL_SECRET);
		const forwarded = new Request(target, {
			method: request.method,
			headers,
			body: request.body,
			redirect: "manual"
		});
		const response = await fetch(forwarded);
		return new Response(response.body, {
			status: response.status,
			statusText: response.statusText,
			headers: response.headers
		});
	};
}
export {
	Router
};
export default {
	fetch: Router.fetch
};
