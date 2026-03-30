const test = require('node:test');
const assert = require('node:assert/strict');
const {
  parseWeekKey,
  compareWeekKeys,
  selectFilesByWeekRange,
} = require('./week-range');

test('parseWeekKey supports canonical file names', () => {
  assert.equal(parseWeekKey('fr_wheat_feat_2021W07.tif'), '2021W07');
});

test('parseWeekKey supports tiled file names', () => {
  assert.equal(
    parseWeekKey('fr_wheat_feat_2020W53-0000000000-0000009984.tif'),
    '2020W53'
  );
});

test('parseWeekKey supports legacy data_NNN file names', () => {
  assert.equal(parseWeekKey('fr_wheat_feat_2025_data_001.tif'), '2025W01');
});

test('compareWeekKeys sorts across year boundaries', () => {
  assert.equal(compareWeekKeys('2020W53', '2021W01') < 0, true);
  assert.equal(compareWeekKeys('2023W10', '2023W10'), 0);
  assert.equal(compareWeekKeys('2023W11', '2023W10') > 0, true);
});

test('selectFilesByWeekRange selects inclusive week range', () => {
  const files = [
    { name: 'fr_wheat_feat_2020W53-0000000000-0000000000.tif' },
    { name: 'fr_wheat_feat_2021W01-0000000000-0000000000.tif' },
    { name: 'fr_wheat_feat_2021W02-0000000000-0000000000.tif' },
    { name: 'fr_wheat_feat_2021W03-0000000000-0000000000.tif' },
  ];
  const selected = selectFilesByWeekRange(files, '2020W53', '2021W02', (f) => f.name);
  assert.deepEqual(selected.map((f) => f.name), [
    'fr_wheat_feat_2020W53-0000000000-0000000000.tif',
    'fr_wheat_feat_2021W01-0000000000-0000000000.tif',
    'fr_wheat_feat_2021W02-0000000000-0000000000.tif',
  ]);
});
