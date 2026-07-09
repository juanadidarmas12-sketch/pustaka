/* Throwaway test for yearToNum() — verifies §3.2 vectors from DESIGN_CONNECTIONS.md.
   Safe to delete after use; not referenced by app.js or sw.js. */
'use strict';

function yearToNum(years) {
  if (!years || typeof years !== 'string') return null;
  const s = years.replace(/±/g, '').trim();

  // "abad ke-N" (century) — SM/M ditentukan dari keberadaan token "SM"
  const abadMatch = s.match(/abad\s+ke-?\s*(\d+)/i);
  if (abadMatch) {
    const n = parseInt(abadMatch[1], 10);
    const isSM = /\bSM\b/i.test(s);
    return isSM ? -(n * 100 - 50) : (n * 100 - 50);
  }

  // angka bermakna pertama (mulai/lahir)
  const numMatch = s.match(/\d{1,4}/);
  if (!numMatch) return null;
  const n = parseInt(numMatch[0], 10);
  const isSM = /\bSM\b/i.test(s);
  return isSM ? -n : n;
}

const vectors = [
  ['±428-348 SM', -428],
  ['121-180 M', 121],
  ['1818-1883', 1818],
  ['±abad ke-6 SM (legendaris)', -550],
  ['Marx 1818-1883, Engels 1820-1895', 1818],
  ['±544-496 SM', -544],
  // vektor tambahan dari data authors.json nyata (regresi sederhana)
  ['1469-1527', 1469],
  ['±55-135 M', 55],
  ['384-322 SM', -384],
  ['tidak ada tahun sama sekali', null],
];

let pass = 0, fail = 0;
vectors.forEach(([input, expected]) => {
  const got = yearToNum(input);
  const ok = got === expected;
  if (ok) pass++; else fail++;
  console.log((ok ? 'PASS' : 'FAIL') + '  yearToNum(' + JSON.stringify(input) + ') = ' + got + '  (expected ' + expected + ')');
});
console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
