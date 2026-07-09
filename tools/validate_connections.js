// Validates the `connections` field added to every author in books/authors.json
// per DESIGN_CONNECTIONS.md §2.6. Node, no deps.
// Checks:
//   1. Every connections[].to with inCatalog:true is really a books/authors.json key.
//      Also flags inCatalog:false entries whose `to` actually DOES match a key
//      (should have been marked true) and vice versa.
//   2. Reciprocity holds for every in-catalog pair (guru<->murid inverse,
//      symmetric types identical on both sides). Reports missing/conflicting.
//   3. No duplicate edges (same (author, to) appearing twice).
//   4. `type` is one of the enum values.
// Prints a summary and exits with code 1 if any violation is found.
'use strict';
const fs = require('fs');
const path = require('path');

const AUTHORS_PATH = path.join(__dirname, '..', 'books', 'authors.json');
const TYPES = new Set(['guru', 'murid', 'sezaman', 'pengaruh', 'menentang', 'kolaborator']);
const INVERSE = { guru: 'murid', murid: 'guru' };
const SYMMETRIC = new Set(['pengaruh', 'sezaman', 'menentang', 'kolaborator']);

function main() {
  const data = JSON.parse(fs.readFileSync(AUTHORS_PATH, 'utf8'));
  const CATALOG = Object.keys(data);
  const catalogSet = new Set(CATALOG);

  const violations = [];
  let totalEdges = 0, inCatalogEdges = 0, freeTextEdges = 0;

  // --- per-edge checks: enum, inCatalog correctness, duplicates ---
  for (const author of CATALOG) {
    const conns = data[author].connections;
    if (!Array.isArray(conns)) {
      violations.push(`${author}: missing or non-array \`connections\` field`);
      continue;
    }
    const seenTo = new Set();
    for (const c of conns) {
      totalEdges++;
      if (c.inCatalog) inCatalogEdges++; else freeTextEdges++;

      if (!TYPES.has(c.type)) {
        violations.push(`${author} -> ${c.to}: invalid type "${c.type}"`);
      }
      const actuallyInCatalog = catalogSet.has(c.to);
      if (c.inCatalog !== actuallyInCatalog) {
        violations.push(`${author} -> ${c.to}: inCatalog=${c.inCatalog} but exact catalog match is ${actuallyInCatalog}`);
      }
      if (c.to === author) {
        violations.push(`${author} -> ${c.to}: self-edge not allowed`);
      }
      if (seenTo.has(c.to)) {
        violations.push(`${author} -> ${c.to}: duplicate edge (same "to" appears twice)`);
      }
      seenTo.add(c.to);
    }
  }

  // --- reciprocity checks (inCatalog:true pairs only) ---
  const byAuthor = new Map();
  for (const author of CATALOG) {
    const m = new Map();
    for (const c of data[author].connections || []) {
      if (c.inCatalog) m.set(c.to, c.type);
    }
    byAuthor.set(author, m);
  }

  const checkedPairs = new Set();
  for (const author of CATALOG) {
    const m = byAuthor.get(author);
    for (const [to, type] of m) {
      if (!catalogSet.has(to)) continue; // shouldn't happen given earlier check
      const pk = author < to ? author + '||' + to : to + '||' + author;
      if (checkedPairs.has(pk)) continue;
      checkedPairs.add(pk);

      const otherMap = byAuthor.get(to);
      const otherType = otherMap ? otherMap.get(author) : undefined;

      if (type === 'guru' || type === 'murid') {
        const expectedOther = INVERSE[type];
        if (otherType === undefined) {
          violations.push(`Reciprocity missing: ${author} -[${type}]-> ${to}, but ${to} has no edge back to ${author} (expected type "${expectedOther}")`);
        } else if (otherType !== expectedOther) {
          violations.push(`Reciprocity conflict: ${author} -[${type}]-> ${to}, but ${to} -[${otherType}]-> ${author} (expected "${expectedOther}")`);
        }
      } else if (SYMMETRIC.has(type)) {
        if (otherType === undefined) {
          violations.push(`Reciprocity missing: ${author} -[${type}]-> ${to}, but ${to} has no edge back to ${author} (expected same type "${type}")`);
        } else if (otherType !== type) {
          violations.push(`Reciprocity conflict: ${author} -[${type}]-> ${to} vs ${to} -[${otherType}]-> ${author} (types differ)`);
        }
      }
    }
  }

  // --- summary ---
  console.log('=== validate_connections summary ===');
  console.log(`Authors checked: ${CATALOG.length}`);
  console.log(`Total edges: ${totalEdges}`);
  console.log(`  in-catalog: ${inCatalogEdges}`);
  console.log(`  free-text : ${freeTextEdges}`);
  console.log(`Violations: ${violations.length}`);
  if (violations.length) {
    console.log('--- violation list ---');
    for (const v of violations) console.log(' - ' + v);
  }
  console.log('====================================');

  if (violations.length > 0) process.exit(1);
}

main();
