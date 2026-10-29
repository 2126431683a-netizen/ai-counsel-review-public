// Original vector portraits: fictional spokespeople with small team silhouettes.
// The objects support the review focus; they never replace the human face.
const SKIN = '#f3c9ad';
const HAIR = '#353743';

function TeamMates({ tint }) {
  return <g className="review-portrait__mates" strokeWidth="2.2">
    <path d="M3 87V73q0-12 13-12t14 12v14" fill={tint}/><path d="M68 87V73q0-12 12-12t13 12v14" fill={tint}/>
    <path d="M7 45q0-12 10-12t10 12v8q0 12-10 12T7 53Z" fill="#e6b99a"/><path d="M7 47V41q1-12 11-10t10 15l-6-2-2-6-5 8Z" fill="#595b6a"/>
    <path d="M70 47q0-12 10-12t10 12v8q0 12-10 12T70 55Z" fill="#f7d9bf"/><path d="M70 46q-2-14 10-14t12 17l-5-2-4-7-7 7Z" fill="#8b6457"/>
    <path d="M13 52h1m7 0h1m54 2h1m7 0h1"/><path d="m13 59 6 1m57 0 6 1"/>
  </g>;
}

const HAIRSTYLES = {
  tech:<path d="M28 38V23q0-15 17-16l5 3 9-4 2 8q11 2 11 15v11l-9-6-4-13-8 8-6-3-7 13Z" fill={HAIR}/>,
  value:<path d="M27 39V29q-1-19 21-19 22 0 22 21v9l-8-3-6-17q-6 10-23 10l2 10Z" fill="#6c5145"/>,
  fun:<path d="M26 38 23 24l8 1-2-12 12 3 8-12 6 9 15-1-4 13 5 7-9 10-4-18-10 7-9-4-5 14Z" fill="#b77a9b"/>,
  think:<path d="M26 43V27q0-19 23-19 23 0 23 22v15l-9-7-2-16-13 9-13-5-1 17Z" fill="#4f445d"/>,
  learn:<path d="M26 39V28q-1-17 21-19 22-3 24 19v14l-10-9-2-12-8 11-10-7-7 16Z" fill="#9c6449"/>,
  editor:<><circle cx="68" cy="15" r="11" fill={HAIR}/><path d="M26 43V27q0-18 23-18 22 0 23 20v15l-8-9-5-15-8 10-16 2-1 12Z" fill={HAIR}/></>,
  custom:<path d="M27 40V28Q27 9 48 9t23 21v12l-9-5-5-16-9 6-9-3-5 17Z" fill="#647488"/>,
};

export default function ReviewPortrait({ identity, compact = false }) {
  const id = identity.id;
  return <svg className="review-portrait" data-portrait={id} viewBox={compact ? '18 0 64 96' : '0 0 96 96'} fill="none" stroke="#252733" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    {!compact && id !== 'editor' && <TeamMates tint={identity.tint}/>}
    <path d="M20 89V77q1-16 21-19h15q20 3 21 19v12Z" fill={identity.accent}/>
    <path d="M40 54v11q8 9 16 0V54" fill={SKIN}/>
    <path d="m35 64 13 14 14-14M48 78v11" stroke={identity.tint}/>
    <ellipse cx="28" cy="43" rx="5" ry="7" fill={SKIN}/><ellipse cx="68" cy="43" rx="5" ry="7" fill={SKIN}/>
    <path d="M29 31q0-17 19-17t19 17v13q-1 21-19 22-18-1-19-22Z" fill={SKIN}/>
    {HAIRSTYLES[id] || HAIRSTYLES.custom}
    <path d={id === 'think' ? 'm37 38 7-2m9 1 7 3' : 'm36 37 8-1m9 0 7 1'}/>
    <path d="m49 43-2 8h4" stroke="#b87d65" strokeWidth="1.7"/>
    {id === 'fun' ? <><path d="m36 44 7-2m11 0 7 2"/><path d="M39 53h19q-3 10-9 10t-10-10Z" fill="#fffdf5"/></> : <><path d="M39 44h1m17 0h1" strokeWidth="3.4"/><path d={id === 'think' ? 'm42 57 10-1' : 'M42 56q7 5 13-1'}/></>}
    {(id === 'tech' || id === 'editor') && <g><rect x="31" y="38" width="15" height="13" rx="4"/><rect x="51" y="38" width="15" height="13" rx="4"/><path d="M46 42h5M27 40h4m35 0h5"/></g>}
    {id === 'tech' && <><path d="m64 85 9-25 5 2-9 26" fill="#ffe28a"/><path d="m73 60 4-5 1 7" fill="#fffdf5"/><path d="M29 77h13v12H29Z" fill="#b7dafa"/><path d="m32 81 3 3 4-5"/></>}
    {id === 'value' && <><rect x="58" y="65" width="23" height="29" rx="4" fill="#ffe6b4" transform="rotate(9 69 80)"/><path d="m63 70 13 2-1 6-13-2Z" fill="#b6c5a9"/><path d="m63 82 1 0m7 1h1m-10 5h1m7 1h1" strokeWidth="3"/><path d="m28 76 11 8"/></>}
    {id === 'fun' && <><path d="M24 41v-8q0-21 24-21t24 21v9" stroke="#ffe28a" strokeWidth="5"/><rect x="21" y="34" width="9" height="19" rx="4" fill="#fbdde9"/><rect x="68" y="34" width="9" height="19" rx="4" fill="#fbdde9"/><path d="m76 11 4-5 2 7 7 1-6 4 1 7-5-4-5 4 1-7-5-4Z" fill="#ffe28a" strokeWidth="1.8"/><path d="m27 76 6 6m5-11 1 9" stroke="#fbdde9"/></>}
    {id === 'think' && <><path d="m61 87-7-16-2-9q1-5 4-1l3 8 5-4q5-3 6 2l-4 18" fill={SKIN}/><path d="m78 15 7-3m-6 11 9 1M71 8l2-5" stroke={identity.accent}/><path d="M26 76h11m-12 6h13" stroke="#e8dff9"/></>}
    {id === 'learn' && <><path d="m33 62 15 8 15-8-4 13-12 4-14-7Z" fill="#d9efdf"/><path d="m52 76 14-4 7 20-16 3Z" fill="#fffdf5"/><path d="m57 80 8-2m-6 7 8-2"/><path d="M74 7h16v16h-7l-6 5v-5h-3Z" fill="#ffe28a" strokeWidth="1.8"/><path d="M80 12q4-3 5 0t-3 4m0 3h.1" strokeWidth="1.9"/></>}
    {id === 'editor' && <><path d="M25 77h29v17H25Z" fill="#fffdf5"/><path d="M31 82h14m-14 6h9"/><path d="m60 88 13-26 6 3-14 25-6 3Z" fill="#ffe28a"/><path d="m73 62 5-4 1 7" fill="#fffdf5"/><path d="m7 35 4 4 9-10" stroke="#93443b" strokeWidth="3.5"/></>}
    {id === 'custom' && <><path d="M33 77h12v-5q8-3 8 4h8v14H33Z" fill="#e5e7ee"/><path d="m78 17 2-5 2 5 5 2-5 2-2 5-2-5-5-2Z" fill="#ffe28a"/></>}
  </svg>;
}
