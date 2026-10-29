import { reviewIdentity } from '../utils/reviewIdentity.js';
import ReviewPortrait from './ReviewPortrait.jsx';
import './ReviewEmblem.css';

export default function ReviewEmblem({ persona = {}, className = '', decorative = true, compact = false }) {
  const identity = reviewIdentity(persona);
  return <span className={`review-emblem review-emblem--${identity.id} ${className}`} data-review-icon={identity.emoji ? 'emoji' : identity.id} style={{ '--emblem-tint':identity.tint, '--emblem-accent':identity.accent }} title={identity.iconName} aria-hidden={decorative ? true : undefined} role={decorative ? undefined : 'img'} aria-label={decorative ? undefined : identity.iconName}>
    {identity.emoji ? <span className="review-emblem__emoji">{identity.emoji}</span> : <ReviewPortrait identity={identity} compact={compact}/>}
  </span>;
}
