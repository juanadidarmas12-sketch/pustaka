const fs = require('fs');
const path = require('path');
const data = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'books', 'authors.json'), 'utf8'));
const out = {};
for (const k of Object.keys(data)) {
  out[k] = { years: data[k].years, influencedBy: data[k].influencedBy || [], influenced: data[k].influenced || [] };
}
fs.writeFileSync(path.join(__dirname, 'condensed.json'), JSON.stringify(out, null, 1));
console.log('done', Object.keys(out).length);
