export function weightCellLevels(weight, count = 20) {
  if (!Number.isFinite(weight) || weight < 0 || weight > 100 || !Number.isInteger(count) || count < 1 || count > 100) return null;
  return Array.from({length:count},(_,i)=>Math.max(0,Math.min(1,weight / 100 * count - i)));
}
