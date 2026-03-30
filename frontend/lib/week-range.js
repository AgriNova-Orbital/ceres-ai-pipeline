const CANONICAL_RE = /^fr_wheat_feat_(\d{4})W(\d{2})\.tif{1,2}$/i;
const TILE_RE = /^fr_wheat_feat_(\d{4})W(\d{2})-\d+-\d+\.tif{1,2}$/i;
const LEGACY_RE = /^fr_wheat_feat_(\d{4})_data_(\d+)\.tif{1,2}$/i;

function parseWeekKey(name) {
  if (!name) return null;
  let m = name.match(CANONICAL_RE);
  if (m) return `${m[1]}W${m[2]}`;
  m = name.match(TILE_RE);
  if (m) return `${m[1]}W${m[2]}`;
  m = name.match(LEGACY_RE);
  if (m) {
    const week = String(Number(m[2])).padStart(2, '0');
    return `${m[1]}W${week}`;
  }
  return null;
}

function weekKeyToNumber(weekKey) {
  const m = /^([0-9]{4})W([0-9]{2})$/i.exec(String(weekKey || ''));
  if (!m) return null;
  return Number(m[1]) * 100 + Number(m[2]);
}

function compareWeekKeys(a, b) {
  const an = weekKeyToNumber(a);
  const bn = weekKeyToNumber(b);
  if (an == null || bn == null) return 0;
  return an - bn;
}

function isWeekKeyInRange(weekKey, start, end) {
  if (!weekKey) return false;
  const wk = weekKeyToNumber(weekKey);
  const s = weekKeyToNumber(start);
  const e = weekKeyToNumber(end);
  if (wk == null || s == null || e == null) return false;
  const lo = Math.min(s, e);
  const hi = Math.max(s, e);
  return wk >= lo && wk <= hi;
}

function selectFilesByWeekRange(files, start, end, getName = (f) => f.name) {
  if (!start || !end) return [];
  return files.filter((file) => isWeekKeyInRange(parseWeekKey(getName(file)), start, end));
}

function summarizeWeekRange(files, start, end, getName = (f) => f.name, getSizeMb = (f) => f.size_mb || 0) {
  const selected = selectFilesByWeekRange(files, start, end, getName);
  const weeks = new Set(selected.map((f) => parseWeekKey(getName(f))).filter(Boolean));
  const totalSizeMb = selected.reduce((sum, f) => sum + Number(getSizeMb(f) || 0), 0);
  return {
    selected,
    weekCount: weeks.size,
    fileCount: selected.length,
    totalSizeMb,
  };
}

module.exports = {
  parseWeekKey,
  compareWeekKeys,
  isWeekKeyInRange,
  selectFilesByWeekRange,
  summarizeWeekRange,
};
