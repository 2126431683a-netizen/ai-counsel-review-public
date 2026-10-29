import { weightCellLevels } from '../utils/reviewWeightCells.js';

export default function ReviewWeightCells({ weight, label = '评分侧重', color, className = '' }) {
  const levels = weightCellLevels(weight);
  if (!levels) return <span className="review-weight-unset">未设置</span>;
  return <span className={`review-weight-cells ${className}`} role="img" aria-label={`${label}：${weight}%`} style={color ? {'--weight-color':color} : undefined}>
    {levels.map((fill,i)=><i key={i} aria-hidden="true" style={{'--cell-fill':`${fill * 100}%`}}/>)}
  </span>;
}
