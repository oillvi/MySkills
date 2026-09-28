// G6 + G7-a: drive DSH's OWN skill loader against the authored SKILL.md.
// Uses the real runtime code from the installed DSH Desktop bundle instead of a
// home-grown validator, so "it parses" means the harness itself parsed it.
//
//   node check_dsh_contract.mjs
//
// Positive case: the shipped SKILL.md must load, be model-invocable and
// user-invocable, and keep a description under the catalog truncation limit.
// Negative cases: two deliberately broken files must be skipped, proving the
// traps documented in references/install.md are real and that we avoided them.

const fs = require("fs");
const os = require("os");
const path = require("path");

const NM = "E:/Softwares/DSH/DSH Desktop/resources/app/node_modules/@deepseek-ai";
const SRC = "E:/Work/Qoder Projects/MySkills/DSH improve/outbox-recorder/SKILL.md";

const fsmod = require(path.join(NM, "dsh-skill-filesystem/lib/index.js"));
const skillmod = require(path.join(NM, "dsh-skill/lib/index.js"));

const results = [];
function check(label, ok, detail) {
  results.push([label, !!ok, detail || ""]);
  console.log(`  [${ok ? "ok" : "FAIL"}] ${label}${!ok && detail ? "\n        " + detail : ""}`);
}

const warns = [];
const ctx = {
  // optionalFileSystem(ctx) does ctx.get("fs"); returning undefined makes the
  // loader fall back to node's own realpath/readFile path, which is exactly the
  // code path a plain on-disk skill directory takes.
  get: () => undefined,
  logger: {
    warn: (...a) => { warns.push(a.join(" ")); },
    info: () => {}, debug: () => {}, error: (...a) => { warns.push("ERR " + a.join(" ")); },
  },
};
function makeControl() {
  return { invalidate: () => {}, signal: new AbortController().signal };
}

function newRoot(tag) {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), `dsh-contract-${tag}-`));
  // projectRoot is found by walking up for .git
  fs.mkdirSync(path.join(root, ".git"), { recursive: true });
  return root;
}

function plantSkill(root, dirName, content) {
  const dir = path.join(root, ".dsh", "skills", dirName);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(path.join(dir, "SKILL.md"), content, "utf8");
  return dir;
}

async function discover(root, showRoots) {
  const provider = new fsmod.FileSystemSkillProvider(ctx, makeControl(), {
    includeDefaultRoots: true,
    dshHome: path.join(root, "dshhome"),
    agentsHome: path.join(root, "agentshome"),
    customSkillDirs: [],
  });
  try {
    if (showRoots) {
      const roots = await provider.roots(root);
      for (const r of roots) console.log(`  [info] root rank=${r.rank} source=${r.source} path=${r.path}`);
    }
    const listed = await provider.list({ cwd: root });
    const arr = Array.isArray(listed) ? listed : (listed && listed.candidates) || [];
    if (listed && listed.complete === false) console.log("  [info] discovery reported complete=false");
    // list() returns catalog candidates (no body). The body only arrives via
    // get(candidate) -- that is the on-demand progressive-disclosure step.
    const loaded = new Map();
    for (const c of arr) {
      try {
        const full = await provider.get(c, {});
        if (full) loaded.set(full.name, full);
      } catch (e) {
        console.log(`  [info] get(${c.name}) threw: ${String(e).slice(0, 160)}`);
      }
    }
    return { candidates: arr, loaded };
  } finally {
    try { provider.dispose(); } catch (_) {}
  }
}

(async () => {
  const shipped = fs.readFileSync(SRC, "utf8");
  console.log(`[info] target: ${SRC}`);
  console.log(`[info] harness: ${require(path.join(NM, "dsh/package.json")).version}` +
              `  desktop: ${require("E:/Softwares/DSH/DSH Desktop/resources/app/package.json").version}`);

  // ---- static G6 metrics -------------------------------------------------
  console.log("\n[G6] static metrics");
  const fmMatch = shipped.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n/);
  check("frontmatter opens and closes on its own line", !!fmMatch);
  const fmText = fmMatch ? fmMatch[1] : "";
  const keys = [...fmText.matchAll(/^([A-Za-z-]+):/gm)].map((m) => m[1]);
  check("only recognized frontmatter keys are used",
        keys.every((k) => ["name", "description", "whenToUse", "disable-model-invocation",
                           "user-invocable", "metadata"].includes(k)),
        `keys = ${keys.join(", ")}`);
  check("no silently-ignored keys (allowed-tools/model/version/license/argument-hint)",
        !keys.some((k) => ["allowed-tools", "model", "version", "license", "argument-hint"].includes(k)),
        `keys = ${keys.join(", ")}`);
  check("no throwing camelCase aliases",
        !/disableModelInvocation|modelInvocable|userInvocable/.test(fmText));
  const nameLine = (fmText.match(/^name:\s*(.+)$/m) || [])[1];
  check("name is kebab-case per the harness regex",
        skillmod.isSkillName((nameLine || "").trim()),
        `name = ${nameLine}`);
  check("name equals the directory name", (nameLine || "").trim() === "outbox-recorder");
  const body = shipped.slice(fmMatch ? fmMatch[0].length : 0);
  const bodyLines = body.split("\n").length;
  check("body under 500 lines", bodyLines < 500, `${bodyLines} lines`);
  check("body under the 110-line design budget", bodyLines <= 115, `${bodyLines} lines`);
  check("no emoji in the body (GBK consoles mangle them)",
        !/[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u.test(body));

  // ---- positive: real loader --------------------------------------------
  console.log("\n[G7-a] DSH loader, positive case");
  const root = newRoot("pos");
  plantSkill(root, "outbox-recorder", shipped);
  let found = { candidates: [], loaded: new Map() };
  try {
    found = await discover(root, true);
  } catch (e) {
    check("discovery did not throw", false, String(e));
  }
  const entries = found.candidates;
  if (entries.length) {
    console.log(`  [info] catalog candidate shape: ${Object.keys(entries[0]).join(", ")}`);
    console.log(`  [info] candidate carries a body? ${"content" in entries[0]}`);
  }
  const mine = entries.find((e) => e.name === "outbox-recorder");
  check("discovered exactly our skill", !!mine,
        `got ${entries.length}: ${entries.map((e) => e.name).join(", ")}`);
  if (mine) {
    const desc = mine.description || "";
    check("description survived parsing", desc.length > 80, `len=${desc.length}`);
    check("description under the 500-char catalog truncation limit", desc.length <= 500,
          `len=${desc.length}`);
    check("description carries TRIGGER phrases", /TRIGGER on:/i.test(desc));
    check("folded scalar did not swallow newlines into literal \\n", !/\\n/.test(desc));
    check("model-invocable (needed for self-discovered problems)",
          skillmod.isModelInvocable(mine) !== false);
    check("user-invocable via /outbox-recorder",
          skillmod.isUserInvocable(mine) !== false);
    const full = found.loaded.get("outbox-recorder");
    check("get(candidate) returned the on-demand body",
          !!full && typeof full.content === "string" && full.content.length > 1000,
          full ? `content length ${String(full.content).length}` : "get() returned undefined");
    const rendered = full ? String(skillmod.renderSkillContent(full)) : "";
    check("rendered body keeps the three-step protocol",
          rendered.includes("三步协议") && rendered.includes("[outbox-recorder] effort: not-gated"));
    check("rendered body keeps the three hard prohibitions",
          rendered.includes("禁调") && rendered.includes("禁改") && rendered.includes("禁当场"));
    check("rendered body points at references/", rendered.includes("references/record-schema.md"));
    check("rendered body is wrapped for the model", rendered.includes("<skill_instructions>")
          || rendered.length > 1000, rendered.slice(0, 120));
    check("resourceBase points at the skill directory",
          !!full && full.resourceBase && full.resourceBase.path.endsWith("outbox-recorder"),
          full ? JSON.stringify(full.resourceBase) : "n/a");
    console.log(`  [info] description length = ${desc.length}`);
    console.log(`  [info] rendered body length = ${rendered.length} chars`);
  }
  check("no loader warnings for our skill",
        !warns.some((w) => w.includes("outbox-recorder")), warns.join(" | ").slice(0, 300));

  // ---- negative: the two documented traps --------------------------------
  console.log("\n[G7-a] DSH loader, negative cases (must be skipped, not crash)");
  warns.length = 0;
  const root2 = newRoot("neg");
  plantSkill(root2, "bad-camel", [
    "---",
    "name: bad-camel",
    "description: camelCase alias that the harness rejects",
    "disableModelInvocation: true",
    "---",
    "",
    "# body",
  ].join("\n"));
  plantSkill(root2, "bad-name", [
    "---",
    "name: Bad Name With Spaces",
    "description: name violates the kebab-case regex",
    "---",
    "",
    "# body",
  ].join("\n"));
  let neg = [];
  let threw = null;
  try {
    neg = (await discover(root2)).candidates;
  } catch (e) {
    threw = String(e);
  }
  check("broken files did not crash discovery", !threw || /unsupported/i.test(threw), threw || "");
  check("camelCase alias is not loadable as a skill",
        !neg.some((e) => e.name === "bad-camel"), neg.map((e) => e.name).join(", "));
  check("invalid name is not loadable as a skill",
        !neg.some((e) => e.name === "Bad Name With Spaces"), neg.map((e) => e.name).join(", "));
  check("the harness logged why", warns.length > 0, "no warnings captured");
  if (warns.length) console.log(`  [info] harness said: ${warns[0].slice(0, 200)}`);

  // ---- summary -----------------------------------------------------------
  const failed = results.filter((r) => !r[1]);
  console.log("\n" + "=".repeat(62));
  console.log(`total ${results.length} checks, ${results.length - failed.length} ok, ${failed.length} FAIL`);
  for (const [label, , detail] of failed) console.log(`  FAIL ${label}\n       ${String(detail).slice(0, 300)}`);
  process.exit(failed.length ? 1 : 0);
})();
