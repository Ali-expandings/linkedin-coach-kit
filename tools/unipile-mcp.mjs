#!/usr/bin/env node
// LinkedIn profile tools over the Unipile API (https://developer.unipile.com/v2.0), as an MCP
// server on stdio. Zero dependencies: Node 18+ built-in fetch, newline-delimited JSON-RPC.
//
// Read:  status, connect_linkedin, read_my_profile, lookup_ids, search_jobs
// Write: update_profile  (dry run unless apply=true)
//
// Deliberately absent: messaging, invitations, connection requests, posts, reactions.
//
// Configuration (first match wins):
//   UNIPILE_API_KEY / UNIPILE_ACCOUNT_ID environment variables
//   tools/unipile.json  {"api_key": "...", "account_id": "acc_..."}   (written by setup.ps1)
// UNIPILE_BASE_URL overrides the API base (tests use a local mock).

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const KIT = path.resolve(HERE, "..");
const CONFIG_FILE = path.join(HERE, "unipile.json");
const BASE = (process.env.UNIPILE_BASE_URL || "https://api.unipile.com/v2").replace(/\/+$/, "");
const TIMEOUT_MS = 90_000;
const LIMITS = { headline: 220, bio: 2600, description: 2000 };
const IMAGE_TYPES = { ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png" };
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;

// ------------------------------------------------------------------ config

function loadConfig() {
  let file = {};
  try {
    file = JSON.parse(fs.readFileSync(CONFIG_FILE, "utf8"));
  } catch {
    /* no file yet */
  }
  return {
    apiKey: process.env.UNIPILE_API_KEY || file.api_key || "",
    accountId: process.env.UNIPILE_ACCOUNT_ID || file.account_id || "",
  };
}

class UserError extends Error {}

// ------------------------------------------------------------------ HTTP

async function api(method, route, { query, body } = {}) {
  const { apiKey } = loadConfig();
  if (!apiKey) {
    throw new UserError(
      "Unipile is not set up: no API key. Run setup.cmd again and paste the Unipile API key, " +
        "or use the browser tools instead."
    );
  }
  const url = new URL(BASE + route);
  for (const [k, v] of Object.entries(query || {})) {
    if (v === undefined || v === null || v === "") continue;
    url.searchParams.set(k, String(v));
  }
  const res = await fetch(url, {
    method,
    headers: {
      "X-API-KEY": apiKey,
      accept: "application/json",
      ...(body ? { "content-type": "application/json" } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(TIMEOUT_MS),
  });
  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { raw: text.slice(0, 2000) };
  }
  if (!res.ok) {
    const detail = data.detail || data.title || data.message || data.raw || "";
    const err = new UserError(`Unipile ${method} ${route} failed: HTTP ${res.status} ${data.type || ""} ${detail}`.trim());
    err.payload = data;
    throw err;
  }
  return data;
}

let cachedAccountId = null; // resolved once per server process, not on every call

async function accountId(explicit) {
  if (explicit) return explicit;
  const cfg = loadConfig();
  if (cfg.accountId) return cfg.accountId;
  if (cachedAccountId) return cachedAccountId;
  const accounts = await linkedinAccounts();
  if (accounts.length === 1) return (cachedAccountId = accounts[0].id);
  if (accounts.length === 0) {
    throw new UserError("No LinkedIn account is linked to Unipile yet. Call connect_linkedin first.");
  }
  throw new UserError(
    `Several LinkedIn accounts are linked: ${accounts.map((a) => a.id).join(", ")}. Pass account_id.`
  );
}

async function linkedinAccounts() {
  const out = [];
  let cursor;
  for (let page = 0; page < 10; page++) {
    const data = await api("GET", "/accounts/", { query: { cursor, limit: 100 } });
    for (const a of data.data || data.items || []) {
      const provider = String(a.provider || a.type || "").toLowerCase();
      if (provider.includes("linkedin")) {
        out.push({ id: a.id, name: a.name || a.display_name || "", status: a.status || a.connection_status || "" });
      }
    }
    cursor = data.next_cursor || data.cursor;
    if (!data.has_more || !cursor) break;
  }
  return out;
}

// ------------------------------------------------------------------ helpers for update_profile

function checkLength(label, value, max, problems) {
  if (typeof value === "string" && value.length > max) {
    problems.push(`${label} is ${value.length} characters; LinkedIn allows ${max}.`);
  }
}

function readImage(p, label, problems) {
  const abs = path.isAbsolute(p) ? p : path.join(KIT, p);
  const ext = path.extname(abs).toLowerCase();
  if (!IMAGE_TYPES[ext]) {
    problems.push(`${label}: use a .jpg or .png file (got "${ext || "no extension"}").`);
    return null;
  }
  let buf;
  try {
    buf = fs.readFileSync(abs);
  } catch {
    problems.push(`${label}: file not found: ${abs}`);
    return null;
  }
  if (buf.length > MAX_IMAGE_BYTES) {
    problems.push(`${label}: ${Math.round(buf.length / 1024 / 1024)} MB is too large (max 8 MB).`);
    return null;
  }
  return { content: buf.toString("base64"), content_type: IMAGE_TYPES[ext], filename: path.basename(abs) };
}

function checkSection(kind, op, problems) {
  if (!op) return;
  if (typeof op !== "object" || Array.isArray(op)) {
    problems.push(`${kind} must be ONE object (one create, edit or delete per call), not a list.`);
    return;
  }
  const operation = op.operation;
  if (!["create", "edit", "delete"].includes(operation)) {
    problems.push(`${kind}.operation must be "create", "edit" or "delete".`);
    return;
  }
  if ((operation === "edit" || operation === "delete") && !op.id) {
    problems.push(`${kind}.${operation} needs the entry's id (from read_my_profile).`);
  }
  if (operation === "create") {
    const required = kind === "experience" ? ["job_title", "company", "start_date"] : ["school", "start_date"];
    for (const k of required) if (!op[k]) problems.push(`${kind}.create needs ${k}.`);
  }
  for (const k of ["job_title", "company", "location", "school", "degree", "field_of_study"]) {
    if (op[k] !== undefined && (typeof op[k] !== "object" || !op[k].name)) {
      problems.push(`${kind}.${k} must be an object like {"name": "..."} (add "id" if you have one).`);
    }
  }
  for (const k of ["start_date", "end_date"]) {
    const d = op[k];
    if (d !== undefined && !(d && Number.isInteger(d.month) && Number.isInteger(d.year) && d.month >= 1 && d.month <= 12)) {
      problems.push(`${kind}.${k} must be {"month": 1-12, "year": YYYY}.`);
    }
  }
  checkLength(`${kind}.description`, op.description, LIMITS.description, problems);
  // Never tell the user's network unless the caller explicitly asked to.
  if (operation !== "delete" && op.notify_network === undefined) op.notify_network = false;
}

function buildUpdate(args) {
  const problems = [];
  const changes = structuredClone(args.changes || {});
  for (const k of ["first_name", "last_name", "description"]) {
    if (k in changes) problems.push(`${k} cannot be changed through LinkedIn's API; leave it out.`);
  }
  const allowedTop = new Set(["bio", "location", "specifics", "picture", "background_picture"]);
  for (const k of Object.keys(changes)) {
    if (!allowedTop.has(k) && !["first_name", "last_name", "description"].includes(k)) {
      problems.push(`Unknown field "${k}". Top-level fields: bio, location, specifics.linkedin.`);
    }
  }
  checkLength("bio (About)", changes.bio, LIMITS.bio, problems);

  const li = changes.specifics?.linkedin;
  if (changes.specifics && !li) problems.push('specifics must look like {"linkedin": {...}}.');
  if (li) {
    checkLength("headline", li.headline, LIMITS.headline, problems);
    checkSection("experience", li.experience, problems);
    checkSection("education", li.education, problems);
    if (li.skills !== undefined) {
      if (!Array.isArray(li.skills) || li.skills.some((s) => !s || !s.name)) {
        problems.push('skills must be a list like [{"name": "Python"}]. Skills can only be added, not removed.');
      }
    }
    if (li.open_to_work && li.open_to_work.visibility === undefined) {
      problems.push('open_to_work.visibility is required: "RECRUITERS_ONLY" (recommended) or "ALL".');
    }
  }

  if (args.picture_path) {
    const img = readImage(args.picture_path, "picture_path", problems);
    if (img) changes.picture = img;
  }
  if (args.background_picture_path) {
    const img = readImage(args.background_picture_path, "background_picture_path", problems);
    if (img) changes.background_picture = img;
  }
  if (Object.keys(changes).length === 0 && problems.length === 0) {
    problems.push("Nothing to change: pass at least one field in changes, or a picture path.");
  }
  return { body: changes, problems };
}

function previewBody(body) {
  const copy = structuredClone(body);
  for (const k of ["picture", "background_picture"]) {
    if (copy[k]?.content) copy[k].content = `<${copy[k].content.length} base64 chars>`;
  }
  return copy;
}

// Unipile returns a lot; keep what a profile coach needs and drop tracking noise.
function slimProfile(p) {
  const li = p.specifics || {};
  const pick = (arr, keys) =>
    Array.isArray(arr) ? arr.map((x) => Object.fromEntries(keys.filter((k) => x[k] !== undefined).map((k) => [k, x[k]]))) : arr;
  return {
    id: p.id,
    public_identifier: p.public_identifier,
    profile_url: p.profile_url,
    name: p.display_name,
    headline: p.description,
    about: p.bio,
    location: p.location,
    websites: p.websites,
    is_open_to_work: li.is_open_to_work,
    industry: li.industry,
    experience: pick(li.experience, ["id", "job_title", "company", "employment_type", "workplace_type", "location", "started_on", "ended_on", "description", "skills"]),
    education: pick(li.education, ["id", "school", "degree", "fields_of_study", "started_on", "ended_on", "grade", "activities", "description"]),
    skills: pick(li.skills, ["name", "endorsement_count"]),
    certifications: li.certifications,
    projects: li.projects,
    languages: li.languages,
    volunteer_experience: li.volunteer_experience,
    throttled_sections: li.throttled_sections,
  };
}

// ------------------------------------------------------------------ tools

const TOOLS = [
  {
    name: "status",
    description:
      "Check the Unipile connection: is the API key valid, which LinkedIn account is linked and is it connected. Call this first.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    run: async () => {
      const accounts = await linkedinAccounts();
      const cfg = loadConfig();
      if (!cfg.accountId && accounts.length === 1) cachedAccountId = accounts[0].id;
      return {
        api_key: "valid",
        linkedin_accounts: accounts,
        default_account_id: cfg.accountId || (accounts.length === 1 ? accounts[0].id : null),
        next_step:
          accounts.length === 0
            ? "No LinkedIn account linked. Call connect_linkedin and send the user the link."
            : "Ready. Use read_my_profile.",
      };
    },
  },
  {
    name: "connect_linkedin",
    description:
      "Create a one-hour Unipile sign-in link the user opens to connect their LinkedIn account. The user signs in on Unipile's page; never ask for their password yourself.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
    run: async () => {
      const expires = new Date(Date.now() + 60 * 60 * 1000).toISOString();
      const data = await api("POST", "/auth/link", {
        body: { providers: ["linkedin"], expires_on: expires, redirect_uri: "https://www.linkedin.com/feed/" },
      });
      return {
        link: data.link,
        expires_on: expires,
        tell_the_user:
          "Open this link, choose LinkedIn and sign in. When it sends you to LinkedIn's feed, you're done — come back and say so.",
      };
    },
  },
  {
    name: "read_my_profile",
    description:
      "Read the user's own LinkedIn profile through the API: headline, about, location, experience and education (with the ids needed to edit them), skills, certifications, projects, languages.",
    inputSchema: {
      type: "object",
      properties: { account_id: { type: "string", description: "Only if several accounts are linked." } },
      additionalProperties: false,
    },
    run: async (a) => {
      const acc = await accountId(a.account_id);
      const p = await api("GET", `/${acc}/users/me`, { query: { with_sections: "linkedin_*", variant: "linkedin_classic" } });
      return slimProfile(p);
    },
  },
  {
    name: "lookup_ids",
    description:
      "Find LinkedIn's ids for a location, company, school, skill, job title, industry or employment type. Use them in update_profile (open_to_work needs job title ids) and search_jobs (locations need ids).",
    inputSchema: {
      type: "object",
      properties: {
        type: {
          type: "string",
          enum: ["LOCATION", "COMPANY", "SCHOOL", "SKILL", "JOB_TITLE", "INDUSTRY", "JOB_FUNCTION", "EMPLOYMENT_TYPE", "SERVICE"],
        },
        keywords: { type: "string" },
        limit: { type: "integer", minimum: 1, maximum: 50 },
        account_id: { type: "string" },
      },
      required: ["type", "keywords"],
      additionalProperties: false,
    },
    run: async (a) => {
      const acc = await accountId(a.account_id);
      return api("GET", `/${acc}/linkedin/search/parameters`, {
        query: { type: a.type, keywords: a.keywords, limit: a.limit || 10 },
      });
    },
  },
  {
    name: "search_jobs",
    description:
      "Search LinkedIn jobs (e.g. internships) to aim the profile at. Location filters need ids from lookup_ids (type LOCATION).",
    inputSchema: {
      type: "object",
      properties: {
        keywords: { type: "string" },
        location: { type: "array", items: { type: "string" }, description: "Location ids from lookup_ids." },
        date_posted: { type: "string", enum: ["PAST_DAY", "PAST_WEEK", "PAST_MONTH"] },
        sort_by: { type: "string", enum: ["RELEVANCE", "DATE"] },
        filters: {
          type: "object",
          description:
            "Any other Unipile jobs-search filter, passed through as-is (workplace_type, seniority, employment_status, easy_apply, ...).",
        },
        limit: { type: "integer", minimum: 1, maximum: 50 },
        account_id: { type: "string" },
      },
      required: ["keywords"],
      additionalProperties: false,
    },
    run: async (a) => {
      const acc = await accountId(a.account_id);
      const body = { keywords: a.keywords, ...(a.filters || {}) };
      if (a.location) body.location = a.location;
      if (a.date_posted) body.date_posted = a.date_posted;
      if (a.sort_by) body.sort_by = a.sort_by;
      return api("POST", `/${acc}/linkedin/search/jobs`, { query: { limit: a.limit || 10 }, body });
    },
  },
  {
    name: "update_profile",
    description: [
      "Change the user's own LinkedIn profile through the API. DRY RUN unless apply is true: without apply it only",
      "validates and returns the exact request. Show the user the dry run, get their yes, then call again with apply: true.",
      "changes is the Unipile request body:",
      '  bio: the About text (<= 2600 chars).   location: a location id from lookup_ids.',
      '  specifics.linkedin.headline (<= 220 chars)',
      '  specifics.linkedin.skills: [{"name": "..."}]  (add only; LinkedIn cannot remove skills here)',
      '  specifics.linkedin.experience: ONE object per call:',
      '    {"operation":"create","job_title":{"name":"..."},"company":{"name":"..."},"start_date":{"month":7,"year":2025},',
      '     "end_date":{...}?, "description":"...", "workplace_type":"ON_SITE|HYBRID|REMOTE"?, "employment_type":"..."?,',
      '     "location":{"name":"..."}?, "media":{"type":"link","url":"https://...","title":"..."}?}',
      '    {"operation":"edit","id":"<from read_my_profile>", ...only the fields to change}',
      '    {"operation":"delete","id":"..."}',
      '  specifics.linkedin.education: ONE object per call, same pattern with school, degree, field_of_study, grade, activities.',
      '  specifics.linkedin.open_to_work: {"job_title":[{"title":"...","id":"<JOB_TITLE id>"}],',
      '     "workplace":[{"type":"REMOTE","location":["<LOCATION id>"]}],"employment_type":["INTERNSHIP"],',
      '     "start_date":"IMMEDIATELY|FLEXIBLE","visibility":"RECRUITERS_ONLY|ALL"}',
      '  specifics.linkedin.custom_link: {"type":"PORTFOLIO|WEBSITE|BLOG|STORE|NEWSLETTER","url":"...","display_on":"PROFILE_ONLY|EVERYWHERE"}',
      "picture_path / background_picture_path: a .jpg/.png in the project (e.g. inbox/photo.jpg).",
      "notify_network defaults to false for experience and education. Name changes are not possible.",
      "Certifications, projects, languages, volunteering, honors and the top-skills order are NOT editable here.",
    ].join("\n"),
    inputSchema: {
      type: "object",
      properties: {
        changes: { type: "object", description: "Unipile update body (see description)." },
        picture_path: { type: "string" },
        background_picture_path: { type: "string" },
        apply: { type: "boolean", description: "false/absent = dry run. true = really change LinkedIn." },
        account_id: { type: "string" },
      },
      additionalProperties: false,
    },
    run: async (a) => {
      const { body, problems } = buildUpdate(a);
      if (problems.length) {
        return { ok: false, applied: false, problems };
      }
      const acc = a.apply ? await accountId(a.account_id) : a.account_id || loadConfig().accountId || "<account_id>";
      const request = { method: "PATCH", url: `${BASE}/${acc}/users/me`, body: previewBody(body) };
      if (!a.apply) {
        return { ok: true, applied: false, dry_run: true, request, next: "Show this to the user. After their yes, call again with apply: true." };
      }
      const response = await api("PATCH", `/${acc}/users/me`, { body });
      return { ok: true, applied: true, request, response };
    },
  },
];

// ------------------------------------------------------------------ MCP (JSON-RPC over stdio)

const SUPPORTED_PROTOCOLS = ["2025-06-18", "2025-03-26", "2024-11-05"];

function send(msg) {
  process.stdout.write(JSON.stringify(msg) + "\n");
}

async function handle(msg) {
  const { id, method, params } = msg;
  if (method === "initialize") {
    const requested = params?.protocolVersion;
    return send({
      jsonrpc: "2.0",
      id,
      result: {
        protocolVersion: SUPPORTED_PROTOCOLS.includes(requested) ? requested : SUPPORTED_PROTOCOLS[0],
        capabilities: { tools: {} },
        serverInfo: { name: "unipile-linkedin", version: "1.0.0" },
      },
    });
  }
  if (method === "notifications/initialized" || method?.startsWith("notifications/")) return;
  if (method === "ping") return send({ jsonrpc: "2.0", id, result: {} });
  if (method === "tools/list") {
    return send({
      jsonrpc: "2.0",
      id,
      result: { tools: TOOLS.map(({ name, description, inputSchema }) => ({ name, description, inputSchema })) },
    });
  }
  if (method === "tools/call") {
    const tool = TOOLS.find((t) => t.name === params?.name);
    if (!tool) {
      return send({ jsonrpc: "2.0", id, error: { code: -32602, message: `Unknown tool: ${params?.name}` } });
    }
    try {
      const out = await tool.run(params.arguments || {});
      return send({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: JSON.stringify(out, null, 2) }] } });
    } catch (e) {
      const text = e instanceof UserError ? e.message : `Unexpected error: ${e?.message || e}`;
      const extra = e?.payload ? `\n${JSON.stringify(e.payload).slice(0, 1500)}` : "";
      return send({ jsonrpc: "2.0", id, result: { content: [{ type: "text", text: text + extra }], isError: true } });
    }
  }
  if (id !== undefined) send({ jsonrpc: "2.0", id, error: { code: -32601, message: `Method not found: ${method}` } });
}

let buffer = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  let nl;
  while ((nl = buffer.indexOf("\n")) !== -1) {
    const line = buffer.slice(0, nl).trim();
    buffer = buffer.slice(nl + 1);
    if (!line) continue;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      send({ jsonrpc: "2.0", id: null, error: { code: -32700, message: "Parse error" } });
      continue;
    }
    handle(msg).catch((e) => send({ jsonrpc: "2.0", id: msg.id ?? null, error: { code: -32603, message: String(e?.message || e) } }));
  }
});
process.stdin.on("end", () => process.exit(0));
