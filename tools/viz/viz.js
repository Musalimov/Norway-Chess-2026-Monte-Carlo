
const D = /*__INJECT_DATA__*/;
const META = /*__INJECT_META__*/;
const NAMES = D.players.map(p=>p.name);
const ru = n => n;
const MLAB = {rapidblitz:"rapid+blitz",blitz:"blitz",rapid:"rapid",classical:"classical"};
const PAL = ["#B01020","#002A5C","#7A7264","#C77F2E","#4A7A6A","#7E4A6A"];
const COLOR = {}; NAMES.forEach((n,i)=>COLOR[n]=PAL[i%PAL.length]);
const ACT_RANK = {}; Object.entries(D.final_standings).sort((a,b)=>b[1]-a[1]).forEach(([n],i)=>ACT_RANK[n]=i+1);
const fmtP = x=>(x*100).toFixed(1)+'%';
const fmtPe = x=>(x*100).toFixed(3)+'%';   // exact, pre-rounding feel
const fmt1 = x=>x.toFixed(1);
const GRID="#CBC3B2";

let tlModel="rapidblitz", gModel="rapidblitz";
const hidden=new Set();
let TLGEO=null;

/* smooth path via Catmull-Rom -> cubic Bezier */
function smoothPath(pts){
  if(pts.length<2) return '';
  let d=`M ${pts[0][0]},${pts[0][1]}`;
  for(let i=0;i<pts.length-1;i++){
    const p0=pts[i-1]||pts[i], p1=pts[i], p2=pts[i+1], p3=pts[i+2]||p2;
    const c1x=p1[0]+(p2[0]-p0[0])/6, c1y=p1[1]+(p2[1]-p0[1])/6;
    const c2x=p2[0]-(p3[0]-p1[0])/6, c2y=p2[1]-(p3[1]-p1[1])/6;
    d+=` C ${c1x},${c1y} ${c2x},${c2y} ${p2[0]},${p2[1]}`;
  }
  return d;
}

function drawTimeline(){
  const svg=document.getElementById('timeline-svg');
  const W=980,H=440,L=64,R=22,T=20,B=52;
  const X=r=>L+r/10*(W-L-R), Y=p=>T+(1-p)*(H-T-B);
  const tl=D.timelines[tlModel].p_win;
  let s='';
  // gridlines + Y ticks
  [0,.1,.2,.3,.4,.5,.6,.7,.8,.9,1].forEach(v=>{
    s+=`<line x1="${L}" y1="${Y(v)}" x2="${W-R}" y2="${Y(v)}" stroke="${GRID}" opacity="${v%0.5===0?0.9:0.4}"/>`;
    if(v%0.1===0) s+=`<text x="${L-8}" y="${Y(v)+4}" font-size="10.5" text-anchor="end">${Math.round(v*100)}%</text>`;
  });
  // X labels
  for(let r=0;r<=10;r++) s+=`<text x="${X(r)}" y="${H-B+20}" font-size="10.5" text-anchor="middle">${r===0?'Before R1':'After R'+r}</text>`;
  // axis titles
  s+=`<text class="axis-title" x="${(L+W-R)/2}" y="${H-6}" text-anchor="middle">round checkpoint</text>`;
  s+=`<text class="axis-title" x="16" y="${(T+H-B)/2}" text-anchor="middle" transform="rotate(-90 16 ${(T+H-B)/2})">win probability (%)</text>`;
  // curves (smoothed, dashed like the original)
  NAMES.forEach(n=>{ if(hidden.has(n))return;
    const pts=tl.map((c,r)=>[X(r),Y(c[n])]);
    const big=ACT_RANK[n]===1;
    s+=`<path d="${smoothPath(pts)}" fill="none" stroke="${COLOR[n]}" stroke-width="${big?3:1.8}" stroke-dasharray="${big?'':'6 4'}" stroke-linejoin="round" opacity="${big?1:.92}"/>`;
    pts.forEach((p,r)=>s+=`<circle cx="${p[0]}" cy="${p[1]}" r="${big?3.4:2.4}" fill="${COLOR[n]}"/>`);
  });
  // hover guide + hit zones
  s+=`<line id="tl-guide" x1="0" y1="${T}" x2="0" y2="${H-B}" stroke="var(--rule)" stroke-dasharray="3 3" opacity="0"/>`;
  const hw=(W-L-R)/10/2;
  for(let r=0;r<=10;r++) s+=`<rect class="hitzone" data-r="${r}" x="${X(r)-hw}" y="${T}" width="${hw*2}" height="${H-T-B}" fill="transparent" style="cursor:crosshair"/>`;
  svg.innerHTML=s;
  TLGEO={W,X}; wireTimelineHover();
}
function wireTimelineHover(){
  const svg=document.getElementById('timeline-svg');
  const tip=document.getElementById('tl-tip');
  const guide=document.getElementById('tl-guide');
  const wrap=svg.parentElement;
  svg.querySelectorAll('.hitzone').forEach(z=>{
    z.addEventListener('mousemove',()=>{
      const r=+z.dataset.r, tl=D.timelines[tlModel].p_win[r];
      const rows=[...NAMES].filter(n=>!hidden.has(n)).sort((a,b)=>tl[b]-tl[a]);
      let html=`<h4>${r===0?'Before R1':'After R'+r}</h4>`;
      rows.forEach((n,i)=>html+=`<div class="trow ${i===0?'hi':''}"><i style="background:${COLOR[n]}"></i><span class="nm">${n}</span><span class="vv">${fmtPe(tl[n])}</span></div>`);
      tip.innerHTML=html;
      guide.setAttribute('x1',TLGEO.X(r));guide.setAttribute('x2',TLGEO.X(r));guide.setAttribute('opacity','0.6');
      const rect=wrap.getBoundingClientRect(), px=(TLGEO.X(r)/TLGEO.W)*rect.width, tw=tip.offsetWidth;
      tip.style.opacity='1';
      let left=px+14; if(left+tw>rect.width) left=px-tw-14;
      tip.style.left=Math.max(4,left)+'px'; tip.style.top='10px';
    });
    z.addEventListener('mouseleave',()=>{tip.style.opacity='0';guide.setAttribute('opacity','0');});
  });
}
function switchUI(id,get,set,after){
  const box=document.getElementById(id);
  box.innerHTML=D.models.map(m=>`<button data-m="${m}" class="${m===get()?'on':''}">${MLAB[m]}</button>`).join('');
  box.querySelectorAll('button').forEach(b=>b.onclick=()=>{set(b.dataset.m);
    box.querySelectorAll('button').forEach(x=>x.classList.toggle('on',x.dataset.m===get()));after();});
}
function chips(){
  const box=document.getElementById('tl-chips');
  box.innerHTML=NAMES.map(n=>`<span class="chip" data-n="${n}"><i style="background:${COLOR[n]}"></i>${n}</span>`).join('');
  box.querySelectorAll('.chip').forEach(c=>c.onclick=()=>{const n=c.dataset.n;
    if(hidden.has(n)){hidden.delete(n);c.classList.remove('off');}else{hidden.add(n);c.classList.add('off');}drawTimeline();});
}
function legendKey(){
  document.getElementById('tl-key').innerHTML=NAMES.map(n=>`<span><i style="border-color:${COLOR[n]}"></i>${n}</span>`).join('');
}
switchUI('tl-models',()=>tlModel,m=>tlModel=m,drawTimeline); chips(); legendKey(); drawTimeline();

function drawStandings(cp){
  const c=D.checkpoints[cp];
  document.getElementById('st-label').textContent=cp===0?'pre-tournament forecast':`rounds 1–${cp} actual, rest simulated`;
  const rows=[...NAMES].sort((a,b)=>c.p_win[b]-c.p_win[a]);
  const mx=Math.max(...NAMES.map(n=>c.p_win[n]));
  let h=`<thead><tr><th>Player</th><th>Score</th><th>P(title)</th><th>E[pts]</th><th>Max</th></tr></thead><tbody>`;
  rows.forEach(n=>{const w=c.p_win[n];
    h+=`<tr class="${ACT_RANK[n]===1?'champ':''}" title="P(title) = ${fmtPe(w)}"><td>${n}</td><td class="num">${fmt1(c.actual_pts[n])}</td>
      <td class="barcell"><div class="bar" style="width:${mx>0?w/mx*100:0}%"></div><span>${fmtP(w)}</span></td>
      <td class="num">${fmt1(c.e_pts[n])}</td><td class="num" style="color:var(--muted)">${fmt1(c.max_reachable[n])}</td></tr>`;});
  document.getElementById('st-table').innerHTML=h+`</tbody>`;
}
/* round-tab selector — replaces the range sliders */
function roundTabs(id, vals, labelFn, initial, onPick){
  const box=document.getElementById(id); if(!box) return;
  let cur=initial;
  function paint(){
    box.querySelectorAll('.rt').forEach(b=>b.classList.toggle('on',+b.dataset.v===cur));
  }
  box.innerHTML=`<span class="rt-lbl">Round</span>`+vals.map(v=>`<button class="rt" data-v="${v}">${labelFn(v)}</button>`).join('');
  box.querySelectorAll('.rt').forEach(b=>b.onclick=()=>{cur=+b.dataset.v;paint();onPick(cur);});
  paint(); onPick(cur);
}
const R0_10=[0,1,2,3,4,5,6,7,8,9,10], R1_10=[1,2,3,4,5,6,7,8,9,10];
roundTabs('st-tabs',R0_10,v=>v===0?'Start':v,0,drawStandings);

function drawRace(cp){
  const c=D.checkpoints[cp];
  const scale=Math.max(...NAMES.map(n=>c.max_reachable[n]),1);
  const rows=[...NAMES].sort((a,b)=>c.actual_pts[b]-c.actual_pts[a]);
  let h='';
  rows.forEach(n=>{const cur=c.actual_pts[n],m=c.max_reachable[n],el=c.eliminated[n];
    h+=`<div class="row ${el?'elim':''}" title="${n}: ${fmt1(cur)} now, up to ${fmt1(m)}"><div class="nm">${n}</div>
      <div class="track"><div class="cur" style="width:${cur/scale*100}%"></div><div class="max" style="left:${m/scale*100}%"></div></div>
      <div class="val">${fmt1(cur)} / max ${fmt1(m)}${el?' ✗':''}</div></div>`;});
  document.getElementById('race-body').innerHTML=h;
}
roundTabs('race-tabs',R0_10,v=>v===0?'Start':v,6,drawRace);

let gRound=1;
function drawGames(rnd){
  gRound=rnd;
  const rd=D.rounds_pred[gModel][rnd-1], CLS=["w","aw","ab","l"];
  const LBL=["White win","armageddon White","armageddon Black","Black win"];
  let h='';
  rd.games.forEach(g=>{
    const res=g.result_type==='classical'?(g.p1_points===3?`${g.p1} 1–0`:`${g.p2} 1–0`)
      :(g.p1_points===1.5?`armageddon · ${g.p1}`:`armageddon · ${g.p2}`);
    let bars=''; g.probs.forEach((p,i)=>bars+=`<div class="${CLS[i]} ${g.actual===i?'hit':''}" data-v="${LBL[i]}: ${fmtPe(p)}" style="width:${p*100}%">${p>0.13?fmtP(p):''}</div>`);
    h+=`<div class="gcard"><div class="gpair">${g.p1} – ${g.p2}</div><div class="gres">${res}</div>
      <div class="wdl">${bars}</div>
      <div class="gmeta"><span>${g.color==='p1_white'?g.p1+' White':'colour 50/50'}</span><span>draw ${fmtP(g.probs[1]+g.probs[2])}</span></div></div>`;});
  document.getElementById('games-body').innerHTML=h;
}
switchUI('g-models',()=>gModel,m=>gModel=m,()=>drawGames(gRound));
roundTabs('g-tabs',R1_10,v=>v,1,drawGames);

/* calibration reliability with point hover */
(function(){
  if(!D.metrics) return;
  const svg=document.getElementById('calib-svg'), tip=document.getElementById('calib-tip'), wrap=svg.parentElement;
  const W=440,H=380,P=46;
  const X=v=>P+v*(W-P-18), Y=v=>H-P-v*(H-P-22);
  let s=`<line x1="${X(0)}" y1="${Y(0)}" x2="${X(1)}" y2="${Y(1)}" stroke="${GRID}" stroke-dasharray="4 4"/>`;
  [0,.25,.5,.75,1].forEach(v=>{s+=`<text x="${X(v)}" y="${H-P+18}" font-size="10" text-anchor="middle">${v}</text><text x="${P-10}" y="${Y(v)+3}" font-size="10" text-anchor="end">${v}</text>`;});
  s+=`<text class="axis-title" x="${W/2}" y="${H-6}" text-anchor="middle">predicted</text>`;
  s+=`<text class="axis-title" x="14" y="${(H-P)/2}" text-anchor="middle" transform="rotate(-90 14 ${(H-P)/2})">observed</text>`;
  const pts=D.metrics.reliability;
  s+=`<polyline points="${pts.map(r=>`${X(r.pred)},${Y(r.obs)}`).join(' ')}" fill="none" stroke="var(--red)" stroke-width="2"/>`;
  pts.forEach((r,i)=>s+=`<circle class="calibpt" data-i="${i}" cx="${X(r.pred)}" cy="${Y(r.obs)}" r="${5+Math.sqrt(r.n)}" fill="var(--red)" opacity="0.7" style="cursor:pointer"/>`);
  svg.innerHTML=s;
  svg.querySelectorAll('.calibpt').forEach(c=>{
    c.addEventListener('mousemove',()=>{const r=pts[+c.dataset.i];
      tip.innerHTML=`<h4>Reliability bin</h4><div class="trow"><span class="nm">predicted</span><span class="vv">${(r.pred*100).toFixed(1)}%</span></div><div class="trow"><span class="nm">observed</span><span class="vv">${(r.obs*100).toFixed(1)}%</span></div><div class="trow"><span class="nm">outcomes</span><span class="vv">${r.n}</span></div>`;
      const rect=wrap.getBoundingClientRect();
      tip.style.opacity='1'; tip.style.left=Math.min((+c.getAttribute('cx')/W)*rect.width+12,rect.width-160)+'px'; tip.style.top='8px';});
    c.addEventListener('mouseleave',()=>tip.style.opacity='0');
  });
})();

/* per-round Brier with bar hover */
(function(){
  if(!D.metrics) return;
  const svg=document.getElementById('brier-svg'), tip=document.getElementById('brier-tip'), wrap=svg.parentElement;
  const br=D.metrics.per_round_brier, uni=D.metrics.uniform_brier, n=br.length, W=440,H=380,P=46;
  const X=i=>P+(i+0.5)/n*(W-P-18), Y=v=>H-P-v/1.0*(H-P-22);
  let s='';
  [0,.25,.5,.75,1].forEach(v=>{s+=`<line x1="${P}" y1="${Y(v)}" x2="${W-18}" y2="${Y(v)}" stroke="${GRID}" opacity="0.5"/><text x="${P-8}" y="${Y(v)+3}" font-size="10" text-anchor="end">${v.toFixed(2)}</text>`;});
  s+=`<line x1="${P}" y1="${Y(uni)}" x2="${W-18}" y2="${Y(uni)}" stroke="var(--navy)" stroke-dasharray="5 4"/><text x="${W-20}" y="${Y(uni)-5}" font-size="9" fill="var(--navy)" text-anchor="end">uniform ${uni}</text>`;
  s+=`<text class="axis-title" x="${W/2}" y="${H-6}" text-anchor="middle">round</text>`;
  s+=`<text class="axis-title" x="14" y="${(H-P)/2}" text-anchor="middle" transform="rotate(-90 14 ${(H-P)/2})">Brier (4 outcomes)</text>`;
  const bw=(W-P-18)/n*0.62;
  br.forEach((v,i)=>{s+=`<rect class="brierbar" data-i="${i}" x="${X(i)-bw/2}" y="${Y(v)}" width="${bw}" height="${Y(0)-Y(v)}" fill="${v<uni?'var(--red)':'var(--navy)'}" opacity="0.82" style="cursor:pointer"/><text x="${X(i)}" y="${H-P+16}" font-size="9" text-anchor="middle">R${i+1}</text>`;});
  svg.innerHTML=s;
  svg.querySelectorAll('.brierbar').forEach(bar=>{
    bar.addEventListener('mousemove',()=>{const i=+bar.dataset.i, v=br[i];
      tip.innerHTML=`<h4>Round ${i+1}</h4><div class="trow"><span class="nm">Brier</span><span class="vv">${v.toFixed(4)}</span></div><div class="trow"><span class="nm">vs uniform</span><span class="vv">${(v<uni?'−':'+')}${Math.abs(v-uni).toFixed(3)}</span></div>`;
      const rect=wrap.getBoundingClientRect();
      tip.style.opacity='1'; tip.style.left=Math.min((X(i)/W)*rect.width+10,rect.width-150)+'px'; tip.style.top='8px';});
    bar.addEventListener('mouseleave',()=>tip.style.opacity='0');
  });
  document.getElementById('brier-note').textContent=`Model mean Brier ${D.metrics.mean_brier} vs ${uni} uniform — sharper in most rounds.`;
})();

/* heatmap with hover */
(function(){
  const sec=document.getElementById('heatmap');
  if(!(D.players[0]&&D.players[0].rank_dist)){sec.style.display='none';return;}
  const n=NAMES.length, rows=[...D.players].sort((a,b)=>ACT_RANK[a.name]-ACT_RANK[b.name]);
  const box=document.getElementById('hm-body'); box.style.gridTemplateColumns=`104px repeat(${n},1fr)`;
  let h=`<div></div>`+Array.from({length:n},(_,i)=>`<div class="h">${i+1}</div>`).join('');
  rows.forEach(p=>{h+=`<div class="n">${p.name}</div>`;
    p.rank_dist.forEach((v,i)=>{const act=ACT_RANK[p.name]===i+1,a=Math.min(v*2.4,1);
      h+=`<div class="c ${act?'act':''}" title="${p.name} · place ${i+1}: ${(v*100).toFixed(2)}%" style="background:rgba(176,16,32,${a.toFixed(2)});color:${v>0.45?'#fff':'var(--ink)'}">${(v*100).toFixed(0)}%</div>`;});});
  box.innerHTML=h;
})();

/* players */
(function(){
  let h=`<thead><tr><th>Player</th><th>Classical</th><th>Rapid</th><th>Blitz</th><th>Style</th><th>Place</th></tr></thead><tbody>`;
  [...D.players].sort((a,b)=>ACT_RANK[a.name]-ACT_RANK[b.name]).forEach(p=>{
    h+=`<tr class="${ACT_RANK[p.name]===1?'champ':''}"><td>${p.name}</td><td class="num">${p.classical}</td>
      <td class="num">${p.rapid}</td><td class="num">${p.blitz}</td><td class="num">${fmt1(p.style)}</td><td class="num">${ACT_RANK[p.name]}</td></tr>`;});
  document.getElementById('pl-table').innerHTML=h+`</tbody>`;
})();
/* model & parameters (appendix B) */
(function(){
  const params=[
    ["White advantage","WA","35 Elo","Rating bonus for the white pieces in classical games."],
    ["Draw base","DBASE","0.70","Draw rate for an even classical game, before adjustments."],
    ["Draw decay","DDEC","0.0018","How fast draws fall off as the rating gap widens."],
    ["Armageddon handicap","ARM_H","−30 Elo","White's penalty in armageddon — Black holds draw odds."],
    ["Form coefficient","K","32","Per-game Elo update from results. Fixed, not tuned on 2026."],
    ["Draw cap","—","0.85","Ceiling on any classical draw probability."],
    ["Min outcome prob","—","0.01","Floor on any single game outcome."],
    ["Simulations","runs","1,000,000","Monte Carlo tournaments run at every checkpoint."],
  ];
  let h=`<thead><tr><th>Parameter</th><th>Symbol</th><th>Value</th><th>What it controls</th></tr></thead><tbody>`;
  params.forEach(p=>h+=`<tr><td>${p[0]}</td><td>${p[1]}</td><td>${p[2]}</td><td>${p[3]}</td></tr>`);
  const t=document.getElementById('hp-table'); if(t) t.innerHTML=h+`</tbody>`;

  const calib=[
    ["RPS + MAP + LOTO-CV","calibration method"],
    ["λ = 0.1","regularisation strength"],
    ["180","training games, 2022–2026"],
    ["0.1902","out-of-sample RPS (2026)"],
    ["0.1944","uniform baseline RPS"],
  ];
  const cs=document.getElementById('calib-strip');
  if(cs) cs.innerHTML=calib.map(c=>`<div class="ci"><div class="ci-num">${c[0]}</div><div class="ci-lbl">${c[1]}</div></div>`).join('');
})();


/* ── masthead + front-page lead (data-driven) ── */
(function(){
  const $=id=>document.getElementById(id);
  const disp=n=>(META.names&&META.names[n])||n;
  function ord(n){const s=["th","st","nd","rd"],v=n%100;return n+(s[(v-20)%10]||s[v]||s[0]);}
  const g=x=>Number.isInteger(x)?(''+x):x.toFixed(1);
  const num=(x,d)=>x.toFixed(d);
  function words(n){const w=["zero","One","Two","Three","Four","Five","Six","Seven","Eight","Nine","Ten","Eleven","Twelve","Thirteen","Fourteen"];return w[n]||(''+n);}

  /* masthead */
  if(META.mast&&$('mastName')){
    const m=META.mast;
    $('mastName').innerHTML = m.length>1 ? `${m[0]} <span class="red">${m.slice(1).join(' ')}</span>` : m[0];
  } else if($('mastName')) $('mastName').textContent=D.tournament;
  if($('mastYear')) $('mastYear').textContent = META.year||'';
  if($('mastVenue')) $('mastVenue').textContent = META.venue||'';
  if($('mastEdition')) $('mastEdition').textContent = META.edition || (META.vol? META.vol+' · Monte Carlo Edition' : 'Monte Carlo Edition');
  const datesEl=$('mastDates'); if(datesEl){ if(META.dates) datesEl.textContent=META.dates; else datesEl.style.display='none'; }
  if($('mastTagline')) $('mastTagline').textContent =
    `${D.iters_main.toLocaleString('en-US')} tournaments per checkpoint · recomputed each round`;

  /* lead story — everything computed from D */
  const lead=$('lead'); if(!lead) return;
  const fs=D.final_standings;
  const ranked=Object.entries(fs).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
  const champ=ranked[0], runner=ranked[1];
  const cp0=D.checkpoints[0].p_win;
  const preRanked=Object.entries(cp0).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
  const fav=preRanked[0], nP=preRanked.length;
  const champPre=cp0[champ], favPre=cp0[fav];
  const favRank=ranked.indexOf(fav)+1, preRankChamp=preRanked.indexOf(champ)+1;
  const score=fs[champ], maxPts=D.checkpoints[0].max_reachable[champ];
  const margin=score-fs[runner], rounds=D.checkpoints.length-1;
  const cn=disp(champ);

  let headline;
  if(champ===fav)            headline=`The <span class="red">favourite</span> delivers`;
  else if(preRankChamp===nP) headline=`The model's <span class="red">longest shot</span> takes the crown`;
  else                       headline=`<span class="red">${cn}</span> defies the forecast`;

  const entry = champ===fav?'entered as the favourite'
              : preRankChamp===nP?'entered as the rank outsider'
              : `entered ${ord(preRankChamp)} of ${nP} in the model's reckoning`;
  const oddsDesc = preRankChamp===nP?'the lowest of the field'
              : preRankChamp===1?'the highest of the field'
              : `${ord(preRankChamp)}-likeliest of ${nP}`;
  const favEnd = favRank===1?'held on to win':`slipped to ${ord(favRank)}`;

  const body=`<span class="dropcap">${cn[0]}</span>${cn} ${entry}. Across `
    +`${D.iters_main.toLocaleString('en-US')} simulated tournaments the engine gave ${cn} just `
    +`<b>${fmtP(champPre)}</b> — ${oddsDesc} — while making ${disp(fav)} a <b>${fmtP(favPre)}</b> favourite. `
    +`${words(rounds)} rounds later ${cn} finished on <b>${g(score)} / ${g(maxPts)}</b>`
    +`${margin>0?`, ${g(margin)} clear of ${disp(runner)}`:''}, and ${disp(fav)} ${favEnd}. `
    +`The pages below rebuild the forecast after every round, and measure how honest it stayed.`;

  const acc = (META.oos_rps!=null)
      ? [num(META.oos_rps,3), 'Out-of-sample RPS · sharper than uniform']
      : (D.metrics? [num(D.metrics.mean_brier,3), `Mean Brier · under ${num(D.metrics.uniform_brier,2)} uniform`] : null);
  const stats=[
    ['accent', fmtP(champPre), "Champion's pre-event title odds"],
    ['',       fmtP(favPre),   `${disp(fav)}'s opening-day odds — finished ${ord(favRank)}`],
    ['',       `${g(score)}<span class="stat-sub">/${g(maxPts)}</span>`, `${cn}'s winning score`],
  ];
  if(acc) stats.push(['', acc[0], acc[1]]);

  lead.innerHTML=`
    <div class="lead-kicker">The result${META.venue?` · ${META.venue}`:''}</div>
    <div class="lead-grid">
      <div class="lead-main">
        <h2 class="lead-head">${headline}</h2>
        <p class="lead-body">${body}</p>
      </div>
      <div class="lead-stats">
        ${stats.map(s=>`<div class="stat ${s[0]}"><div class="stat-num">${s[1]}</div><div class="stat-lbl">${s[2]}</div></div>`).join('')}
      </div>
    </div>`;
})();
