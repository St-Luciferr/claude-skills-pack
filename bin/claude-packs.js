#!/usr/bin/env node
'use strict';

/*
 * claude-packs — install Claude Code skill/agent bundles into a project or user config.
 *
 * Zero runtime dependencies (Node >= 16). Bundles live in ../bundles relative to this
 * file; each bundle has a bundle.json manifest plus skills/ and agents/ directories.
 */

const fs = require('fs');
const path = require('path');
const os = require('os');
const { execSync } = require('child_process');

const PKG_ROOT = path.resolve(__dirname, '..');
const BUNDLES_DIR = path.join(PKG_ROOT, 'bundles');
const RECEIPT = '.claude-packs.json'; // written into each target .claude dir

// ---------- pretty output ----------
const useColor = process.stdout.isTTY && !process.env.NO_COLOR;
const c = (code, s) => (useColor ? `\x1b[${code}m${s}\x1b[0m` : s);
const bold = (s) => c('1', s);
const dim = (s) => c('2', s);
const green = (s) => c('32', s);
const yellow = (s) => c('33', s);
const cyan = (s) => c('36', s);
const red = (s) => c('31', s);

function die(msg) {
  console.error(red('error: ') + msg);
  process.exit(1);
}

// ---------- version ----------
function cliVersion() {
  try {
    return JSON.parse(fs.readFileSync(path.join(PKG_ROOT, 'package.json'), 'utf8')).version || '0.0.0';
  } catch {
    return '0.0.0';
  }
}

// ---------- bundle discovery ----------
function loadBundles() {
  if (!fs.existsSync(BUNDLES_DIR)) return [];
  return fs
    .readdirSync(BUNDLES_DIR, { withFileTypes: true })
    .filter((d) => d.isDirectory())
    .map((d) => {
      const manifestPath = path.join(BUNDLES_DIR, d.name, 'bundle.json');
      if (!fs.existsSync(manifestPath)) return null;
      let m;
      try {
        m = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
      } catch (e) {
        console.error(yellow(`warning: skipping ${d.name}: invalid bundle.json (${e.message})`));
        return null;
      }
      m.name = m.name || d.name;
      m.dir = path.join(BUNDLES_DIR, d.name);
      m.skills = m.skills || [];
      m.agents = m.agents || [];
      return m;
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
}

function findBundle(bundles, name) {
  const b = bundles.find((x) => x.name === name);
  if (!b) {
    die(`unknown bundle "${name}". Run "claude-packs list" to see available bundles.`);
  }
  return b;
}

// ---------- target resolution ----------
function resolveTarget(opts) {
  if (opts.user) return path.join(os.homedir(), '.claude');
  if (opts.project !== undefined) {
    const dir = opts.project || process.cwd();
    return path.join(path.resolve(dir), '.claude');
  }
  // default: user-level
  return path.join(os.homedir(), '.claude');
}

// ---------- receipt (install tracking) ----------
function readReceipt(target) {
  const p = path.join(target, RECEIPT);
  if (!fs.existsSync(p)) return { bundles: {} };
  try {
    const r = JSON.parse(fs.readFileSync(p, 'utf8'));
    r.bundles = r.bundles || {};
    return r;
  } catch {
    return { bundles: {} };
  }
}

function writeReceipt(target, receipt) {
  fs.mkdirSync(target, { recursive: true });
  fs.writeFileSync(path.join(target, RECEIPT), JSON.stringify(receipt, null, 2) + '\n');
}

// ---------- fs helpers ----------
function copyDir(src, dest) {
  fs.rmSync(dest, { recursive: true, force: true });
  fs.cpSync(src, dest, { recursive: true }); // preserves file modes
}

function promptYesNo(question) {
  if (!process.stdin.isTTY) return false;
  try {
    // synchronous prompt via /dev/tty
    const answer = execSync(`printf '%s' ${JSON.stringify(question + ' [y/N] ')} > /dev/tty; head -n1 < /dev/tty`, {
      encoding: 'utf8',
    }).trim();
    return /^y(es)?$/i.test(answer);
  } catch {
    return false;
  }
}

// ---------- commands ----------
function cmdList(bundles, opts) {
  if (!bundles.length) {
    console.log('No bundles found.');
    return;
  }
  const target = resolveTarget(opts);
  const receipt = readReceipt(target);
  console.log(bold('\nAvailable bundles') + dim(`  (installed status vs ${prettyTarget(target)})\n`));
  for (const b of bundles) {
    const installed = receipt.bundles[b.name];
    const badge = installed
      ? green(`✓ installed`) + dim(installed.version && installed.version !== b.version ? ` (${installed.version} → ${b.version} available)` : '')
      : dim('not installed');
    console.log(`  ${bold(cyan(b.name))} ${dim('v' + (b.version || '0.0.0'))}  ${badge}`);
    if (b.title) console.log(`    ${b.title}`);
    console.log(
      dim(`    ${b.skills.length} skill${b.skills.length === 1 ? '' : 's'}, ${b.agents.length} agent${b.agents.length === 1 ? '' : 's'}`) +
        (b.tags && b.tags.length ? dim(`  ·  ${b.tags.join(', ')}`) : '')
    );
  }
  console.log(dim('\nInstall with:  ') + 'claude-packs install <bundle> [--user | --project [dir]]\n');
}

function cmdInfo(bundles, args) {
  const name = args._[0];
  if (!name) die('usage: claude-packs info <bundle>');
  const b = findBundle(bundles, name);
  console.log('\n' + bold(cyan(b.name)) + dim('  v' + (b.version || '0.0.0')));
  if (b.title) console.log(bold(b.title));
  if (b.description) console.log('\n' + wrap(b.description, 80));
  if (b.tags && b.tags.length) console.log('\n' + dim('tags: ') + b.tags.join(', '));
  console.log('\n' + bold('Skills') + dim(` (${b.skills.length})`));
  for (const s of b.skills) console.log('  ' + green('•') + ' ' + s + describeSkill(b, s));
  console.log('\n' + bold('Agents') + dim(` (${b.agents.length})`));
  for (const a of b.agents) console.log('  ' + green('•') + ' ' + a);
  console.log('');
}

function describeSkill(b, skill) {
  // pull the one-line title from the skill's SKILL.md description if present
  const p = path.join(b.dir, 'skills', skill, 'SKILL.md');
  if (!fs.existsSync(p)) return '';
  const txt = fs.readFileSync(p, 'utf8').slice(0, 400);
  const m = txt.match(/description:\s*>?\s*\n?\s*(.+)/);
  return m ? dim('  — ' + m[1].trim().replace(/\s+/g, ' ').slice(0, 60)) : '';
}

function cmdInstall(bundles, args, opts) {
  const names = args._;
  if (!names.length) die('usage: claude-packs install <bundle...> [--user | --project [dir]] [--force]');
  const target = resolveTarget(opts);
  const receipt = readReceipt(target);
  let anyInstalled = false;

  for (const name of names) {
    const b = findBundle(bundles, name);
    console.log(bold(`\nInstalling ${cyan(b.name)} v${b.version || '0.0.0'} → ${prettyTarget(target)}`));

    const files = { skills: [], agents: [] };

    // skills (directories)
    for (const s of b.skills) {
      const src = path.join(b.dir, 'skills', s);
      if (!fs.existsSync(src)) {
        console.error(yellow(`  ! skill "${s}" missing from bundle, skipping`));
        continue;
      }
      const dest = path.join(target, 'skills', s);
      if (fs.existsSync(dest) && !opts.force && !isOwned(receipt, b.name, 'skills', s)) {
        if (!promptYesNo(`  ${dest} exists and is not tracked by claude-packs. Overwrite?`)) {
          console.log(dim(`  - skipped skill ${s}`));
          continue;
        }
      }
      fs.mkdirSync(path.join(target, 'skills'), { recursive: true });
      copyDir(src, dest);
      files.skills.push(s);
      console.log('  ' + green('+') + ` skill ${s}`);
    }

    // agents (single .md files)
    for (const a of b.agents) {
      const src = path.join(b.dir, 'agents', a + '.md');
      if (!fs.existsSync(src)) {
        console.error(yellow(`  ! agent "${a}" missing from bundle, skipping`));
        continue;
      }
      const dest = path.join(target, 'agents', a + '.md');
      if (fs.existsSync(dest) && !opts.force && !isOwned(receipt, b.name, 'agents', a)) {
        if (!promptYesNo(`  ${dest} exists and is not tracked by claude-packs. Overwrite?`)) {
          console.log(dim(`  - skipped agent ${a}`));
          continue;
        }
      }
      fs.mkdirSync(path.join(target, 'agents'), { recursive: true });
      fs.copyFileSync(src, dest);
      files.agents.push(a);
      console.log('  ' + green('+') + ` agent ${a}`);
    }

    receipt.bundles[b.name] = { version: b.version || '0.0.0', skills: files.skills, agents: files.agents };
    anyInstalled = true;
  }

  if (anyInstalled) {
    writeReceipt(target, receipt);
    console.log(green('\n✓ Done.') + ' Restart Claude Code — skills and agents load at session start.\n');
  }
}

function isOwned(receipt, bundleName, kind, item) {
  const b = receipt.bundles[bundleName];
  return b && b[kind] && b[kind].includes(item);
}

function cmdUninstall(bundles, args, opts) {
  const names = args._;
  if (!names.length) die('usage: claude-packs uninstall <bundle...> [--user | --project [dir]]');
  const target = resolveTarget(opts);
  const receipt = readReceipt(target);
  let changed = false;

  for (const name of names) {
    const rec = receipt.bundles[name];
    if (!rec) {
      console.log(yellow(`  ${name} is not installed at ${prettyTarget(target)}`));
      continue;
    }
    console.log(bold(`\nRemoving ${cyan(name)} from ${prettyTarget(target)}`));
    for (const s of rec.skills || []) {
      const p = path.join(target, 'skills', s);
      if (fs.existsSync(p)) {
        fs.rmSync(p, { recursive: true, force: true });
        console.log('  ' + red('-') + ` skill ${s}`);
      }
    }
    for (const a of rec.agents || []) {
      const p = path.join(target, 'agents', a + '.md');
      if (fs.existsSync(p)) {
        fs.rmSync(p, { force: true });
        console.log('  ' + red('-') + ` agent ${a}`);
      }
    }
    delete receipt.bundles[name];
    changed = true;
  }

  if (changed) {
    writeReceipt(target, receipt);
    console.log(green('\n✓ Uninstalled.\n'));
  }
}

function cmdUpdate(bundles, args, opts) {
  const target = resolveTarget(opts);
  const receipt = readReceipt(target);
  const names = args._.length ? args._ : Object.keys(receipt.bundles);
  if (!names.length) {
    console.log(`Nothing installed at ${prettyTarget(target)}.`);
    return;
  }
  console.log(dim('Re-installing latest bundle content over existing installs...'));
  // reinstall each (force over owned files) to pick up newer content from this package
  cmdInstall(bundles, { _: names }, { ...opts, force: true });
}

function cmdInstalled(bundles, opts) {
  const target = resolveTarget(opts);
  const receipt = readReceipt(target);
  const names = Object.keys(receipt.bundles);
  if (!names.length) {
    console.log(`No bundles installed at ${prettyTarget(target)}.`);
    return;
  }
  console.log(bold(`\nInstalled at ${prettyTarget(target)}:\n`));
  for (const name of names) {
    const rec = receipt.bundles[name];
    console.log(`  ${cyan(name)} ${dim('v' + rec.version)}  ${dim(`(${(rec.skills || []).length} skills, ${(rec.agents || []).length} agents)`)}`);
  }
  console.log('');
}

// ---------- misc ----------
function prettyTarget(target) {
  const home = os.homedir();
  if (target === path.join(home, '.claude')) return '~/.claude (user)';
  return target.replace(home, '~');
}

function wrap(text, width) {
  const words = text.replace(/\s+/g, ' ').trim().split(' ');
  const lines = [];
  let line = '';
  for (const w of words) {
    if ((line + ' ' + w).trim().length > width) {
      lines.push(line.trim());
      line = w;
    } else {
      line += ' ' + w;
    }
  }
  if (line.trim()) lines.push(line.trim());
  return lines.join('\n');
}

function parseArgs(argv) {
  const opts = { force: false };
  const _ = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '--user' || a === '-u') opts.user = true;
    else if (a === '--project' || a === '-p') {
      const next = argv[i + 1];
      if (next && !next.startsWith('-')) {
        opts.project = next;
        i++;
      } else {
        opts.project = '';
      }
    } else if (a === '--force' || a === '-f') opts.force = true;
    else if (a === '--help' || a === '-h') opts.help = true;
    else if (a === '--version' || a === '-V') opts.version = true;
    else if (a.startsWith('-')) die(`unknown option: ${a}`);
    else _.push(a);
  }
  return { _, opts };
}

function usage() {
  console.log(`
${bold('claude-packs')} ${dim('v' + cliVersion())} — install Claude Code skill/agent bundles

${bold('Usage')}
  claude-packs <command> [bundles...] [options]

${bold('Commands')}
  ${cyan('list')}                       list available bundles and install status
  ${cyan('info')} <bundle>              show a bundle's skills, agents, and description
  ${cyan('install')} <bundle...>        install one or more bundles
  ${cyan('uninstall')} <bundle...>      remove installed bundles
  ${cyan('update')} [bundle...]         re-copy latest bundle content over installs
  ${cyan('installed')}                  list bundles installed at the target

${bold('Options')}
  -u, --user                 install into ~/.claude  ${dim('(default; all projects)')}
  -p, --project [dir]        install into <dir>/.claude  ${dim('(default dir: cwd)')}
  -f, --force                overwrite without prompting
  -h, --help                 show this help
  -V, --version              print version

${bold('Examples')}
  claude-packs list
  claude-packs install aws-connect --user
  claude-packs install aws-connect --project .
  claude-packs uninstall aws-connect --project ~/my-app

${dim('Run directly from GitHub (no install needed):')}
  npx github:OWNER/REPO list
`);
}

// ---------- main ----------
function main() {
  const argv = process.argv.slice(2);
  const { _, opts } = parseArgs(argv);

  if (opts.version) {
    console.log(cliVersion());
    return;
  }

  const command = _.shift();

  if (!command || opts.help || command === 'help') {
    usage();
    return;
  }

  const bundles = loadBundles();
  const rest = { _, opts };

  switch (command) {
    case 'list':
    case 'ls':
      return cmdList(bundles, opts);
    case 'info':
    case 'show':
      return cmdInfo(bundles, rest);
    case 'install':
    case 'add':
      return cmdInstall(bundles, rest, opts);
    case 'uninstall':
    case 'remove':
    case 'rm':
      return cmdUninstall(bundles, rest, opts);
    case 'update':
    case 'upgrade':
      return cmdUpdate(bundles, rest, opts);
    case 'installed':
      return cmdInstalled(bundles, opts);
    default:
      die(`unknown command "${command}". Run "claude-packs --help".`);
  }
}

main();
