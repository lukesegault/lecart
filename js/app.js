(async()=>{
// data.json and the event list change once a day: the version in <meta name="data-version"> (rewritten by build_data.py) lets browsers cache them.
const VER=(document.querySelector('meta[name="data-version"]')||{}).content, get=u=>fetch(VER?u+"?v="+VER:u).then(r=>{ if(!r.ok) throw new Error(u); return r.json() });
let DATA,T;
try{ const [d,fr,en]=await Promise.all([get("data.json"),get("i18n/fr.json"),get("i18n/en.json")]); DATA=d; T={fr,en}; }
catch(e){ document.getElementById("board").innerHTML="<p style=\"padding:16px\">Data could not be loaded. / Les données n'ont pas pu être chargées.</p>"; return; }
const MARKET=DATA.markets.candidates;
let EVENTS=[]; try{ EVENTS=await get("data/events.json"); EVENTS.sort((a,b)=>a.date<b.date?-1:1); }catch(e){}

let lang=(()=>{try{const s=localStorage.getItem("lecart-lang");if(s==="fr"||s==="en")return s}catch(e){} return (navigator.language||"fr").toLowerCase().startsWith("fr")?"fr":"en"})();
const state={q:"qual",u:"mid",all:false};
const t=k=>T[lang][k];
const tf=(k,o)=>t(k).replace(/\{(\w+)\}/g,(m,x)=>x in o?o[x]:m);   // strings with {name} slots

// Poll-derived numbers (win/qual per candidate and uncertainty level, average score) are computed by scripts/build_data.py.
const sim=l=>DATA.sim[l];

const nb="\u00a0";
// Dates and figures of the page text come from data.json. Keep in step with fr_figures() in scripts/build_data.py.
const longDate=iso=>{ const [y,m,d]=iso.split("-"); return (lang==="fr"&&+d===1?"1er":+d)+" "+t("monthsL")[+m-1]+" "+y };
const money=v=>{
  if(v>=1e6){ const m=Math.round(v/(v<1e7?1e5:1e6))/(v<1e7?10:1), s=lang==="fr"?String(m).replace(".",","):String(m);
    return lang==="fr"?s+nb+(m<2?"million":"millions")+nb+"de"+nb+"$":"$"+s+" million"; }
  const k=Math.round(v/1000)*1000; return lang==="fr"?String(k).replace(/\B(?=(\d{3})+$)/g,nb)+nb+"$":"$"+k.toLocaleString("en-GB");
};
function figures(){
  const ends=DATA.polls.map(p=>p.end).sort(), lo=ends[0], hi=ends[ends.length-1], mk=DATA.markets;
  const from=lo.slice(0,4)===hi.slice(0,4)?longDate(lo).replace(/ \d{4}$/,""):longDate(lo);
  return {upd:longDate(DATA.updated),year:DATA.updated.slice(0,4),snap:longDate(mk.snapshot),n:DATA.polls.length,from,to:longDate(hi),
    vq:mk.volume?money(mk.volume.qual):"–",vw:mk.volume?money(mk.volume.win):"–",
    sum:mk.qualSum==null?"–":Math.round(mk.qualSum/10)*10+(lang==="fr"?nb+"%":"%")};
}
const fill=s=>{ const F=figures(); return s.replace(/\{\{(\w+)\}\}/g,(_,k)=>F[k]) };
const pct=x=> x>0&&x<1 ? (lang==="fr"?"<1"+nb+"%":"<1%") : Math.round(x)+(lang==="fr"?nb+"%":"%");
const pct1=x=> lang==="fr" ? x.toFixed(1).replace(".",",")+nb+"%" : x.toFixed(1)+"%";
const surname=n=>({"Marine Le Pen":"Le Pen","Jean-Luc Mélenchon":"Mélenchon","Dominique de Villepin":"de Villepin","Nicolas Dupont-Aignan":"Dupont-Aignan"}[n]||n.split(" ").slice(-1)[0]);

function rows(q=state.q,u=state.u){
  const S=sim(u);
  return MARKET.map(m=>{const s=S[m.c], a=DATA.avg[m.c]; return {c:m.c,f:m.f,market:m[q],poll:s?s[q]:null,avg:a?a[0]:null,n:a?a[1]:0}})
   .sort((x,y)=>Math.max(y.market,y.poll||0)-Math.max(x.market,x.poll||0));
}
function applyStatic(){
  document.documentElement.lang=lang;
  document.title = lang==="fr" ? "L'Écart · Marchés vs sondages, présidentielle 2027" : "L'Écart · Markets vs polls, French election 2027";
  document.querySelectorAll("[data-i]").forEach(el=>{const v=t(el.dataset.i); if(typeof v==="string") el.innerHTML=fill(v)});
  document.querySelectorAll("[data-lang]").forEach(b=>b.setAttribute("aria-pressed",b.dataset.lang===lang));
  document.getElementById("families").innerHTML=Object.entries(t("fam")).map(([k,v])=>`<span><i style="background:var(--${k})"></i>${v}</span>`).join("");
}
function renderBoard(){
  const R=rows(), shown=state.all?R:R.slice(0,8);
  const ticks=[0,25,50,75,100].map(x=>`<span style="left:${x}%">${x}</span>`).join("");
  let h=`<div class="axis" aria-hidden="true"><div></div><div class="ticks">${ticks}</div><div style="text-align:right">${t("gapCol")}</div></div>`;
  shown.forEach(r=>{
    const sub=r.avg!=null?tf("inPolls",{a:pct1(r.avg),n:r.n}):t("notPolled");
    let track=`<div class="grid"></div><div class="base"></div>`, gap;
    if(r.poll==null){
      track+=`<div class="dot m" style="left:${r.market}%"></div>`;
      gap=`<b class="flat">${pct(r.market)}</b><br>${t("marketsOnly")}`;
    } else {
      const lo=Math.min(r.poll,r.market), hi=Math.max(r.poll,r.market), d=r.market-r.poll;
      const col = d>=0 ? "var(--market-soft)" : "var(--poll-soft)";
      track+=`<div class="gapbar" style="left:${lo}%;width:${hi-lo}%;background:${col}"></div><div class="dot p" style="left:${r.poll}%"></div><div class="dot m" style="left:${r.market}%"></div>`;
      const cls=Math.abs(d)<2?"flat":d>0?"up":"down";
      gap=`<b class="${cls}">${d>=0?"+":"−"}${Math.abs(Math.round(d))}</b><br>${pct(r.poll)} / ${pct(r.market)}`;
    }
    const label=`${r.c}. ${t("polls")} ${r.poll==null?"–":pct(r.poll)}, ${t("markets")} ${pct(r.market)}`;
    h+=`<div class="row" role="group" aria-label="${label}"><div class="name"><span class="swatch" style="background:var(--${r.f})"></span><div><strong>${r.c}</strong><small>${sub}</small></div></div><div class="track">${track}</div><div class="gapv">${gap}</div></div>`;
  });
  document.getElementById("board").innerHTML=h;
  const more=document.getElementById("more"); more.textContent=state.all?t("less"):t("more"); more.setAttribute("aria-expanded",state.all);
  renderGaps(R);
}
function renderGaps(R){
  const verb=state.q==="qual"?t("verbQ"):t("verbW");
  const top=R.filter(r=>r.poll!=null).sort((a,b)=>Math.abs(b.market-b.poll)-Math.abs(a.market-a.poll)).slice(0,3);
  document.getElementById("gaps").innerHTML=top.map(r=>{
    const d=r.market-r.poll, D=Math.abs(Math.round(d)), txt=tf(d>0?"gapUp":"gapDown",{s:surname(r.c),v:verb,d:D});
    return `<div class="gap-item" style="--c:var(--${r.f})"><div class="big" style="color:${d>0?"var(--market)":"var(--poll)"}">${d>0?"+":"−"}${D}</div><h3>${r.c}</h3><div class="nums">${t("polls")} ${pct(r.poll)}, ${t("markets")} ${pct(r.market)}</div><p>${txt}</p></div>`}).join("");
}
function renderSpot(first){
  const R=rows("win","mid").filter(r=>r.poll!=null).sort((a,b)=>Math.abs(b.market-b.poll)-Math.abs(a.market-a.poll));
  const r=R[0], lo=Math.min(r.poll,r.market), hi=Math.max(r.poll,r.market);
  document.getElementById("spotWho").textContent=r.c;
  document.querySelector("#spotP b").textContent=pct(r.poll);
  document.querySelector("#spotM b").textContent=pct(r.market);
  document.getElementById("spotCap").textContent=tf("spotCap",{n:surname(r.c)});
  const go=()=>{ spotP.style.left=r.poll+"%"; spotM.style.left=r.market+"%"; spotFill.style.left=lo+"%"; spotFill.style.width=(hi-lo)+"%"; };
  first ? requestAnimationFrame(()=>setTimeout(go,250)) : go();
}
const monthLab=(m,i)=>{const [yy,mm]=m.split("-"); return t("months")[+mm-1]+((mm==="01"||i===0)?" "+yy.slice(2):"")};
// Path through the non-null points of s; two points more than `gap` indices apart are not joined.
function pathOf(s,x,y,gap=1){
  let d="",prev=-1,last=null;
  s.forEach((v,i)=>{ if(v==null) return; d+=(prev>=0&&i-prev<=gap?"L":"M")+x(i).toFixed(1)+" "+y(v).toFixed(1)+" "; prev=i; last=i });
  return {d,last};
}
function trend(){
  const svg=document.getElementById("trend"), TR=DATA.trend, W=900,H=390,ml=44,mr=160,mt=24,mb=40;
  svg.setAttribute("aria-label",t("chartAria"));
  const fam={"Marine Le Pen":"var(--far-right)","Jordan Bardella":"var(--faint)","Édouard Philippe":"var(--centre)","Jean-Luc Mélenchon":"var(--far-left)","Raphaël Glucksmann":"var(--left)","Gabriel Attal":"var(--right)","Bruno Retailleau":"var(--green)"};
  const dash={"Jordan Bardella":"5 4"};
  const months=TR.months, x=i=>ml+i*(W-ml-mr)/(months.length-1), y=v=>mt+(1-v/40)*(H-mt-mb);
  let g="";
  [0,10,20,30,40].forEach(v=>{g+=`<line x1="${ml}" x2="${W-mr}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/><text x="${ml-10}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="var(--muted)">${v}${lang==="fr"?" %":"%"}</text>`});
  months.forEach((m,i)=>{g+=`<text x="${x(i)}" y="${H-14}" text-anchor="middle" font-size="12" fill="var(--muted)">${monthLab(m,i)}</text>`});
  const iJul=months.indexOf("2026-07");
  if(iJul>=0){ g+=`<rect x="${x(iJul)}" y="${mt}" width="${x(months.length-1)-x(iJul)}" height="${H-mt-mb}" fill="var(--soft)"/><line x1="${x(iJul)}" x2="${x(iJul)}" y1="${mt}" y2="${H-mb}" stroke="var(--faint)" stroke-dasharray="3 4"/><text x="${x(iJul)+8}" y="${H-mb-24}" font-size="12" fill="var(--muted)">${t("ev1")}</text><text x="${x(iJul)+8}" y="${H-mb-9}" font-size="12" fill="var(--muted)">${t("ev2")}</text>`;
    // redraw grid lines over band
    [10,20,30,40].forEach(v=>{g+=`<line x1="${x(iJul)}" x2="${W-mr}" y1="${y(v)}" y2="${y(v)}" stroke="var(--rule)"/>`}); }
  const ends=[];
  for(const c in TR.series){
    const s=TR.series[c], {d,last}=pathOf(s,x,y);
    g+=`<g class="ser" data-c="${c}" style="transition:opacity .2s"><path d="${d}" fill="none" stroke="${fam[c]}" stroke-width="2.75" ${dash[c]?`stroke-dasharray="${dash[c]}"`:""} stroke-linejoin="round" stroke-linecap="round"/>`;
    s.forEach((v,i)=>{if(v!=null)g+=`<circle cx="${x(i)}" cy="${y(v)}" r="${i===last?4:2.6}" fill="${fam[c]}" stroke="var(--surface)" stroke-width="1.5"/>`});
    g+="</g>"; ends.push({c,yy:y(s[last]),xx:x(last),col:fam[c],v:s[last]});
  }
  ends.sort((a,b)=>a.yy-b.yy); for(let i=1;i<ends.length;i++) if(ends[i].yy-ends[i-1].yy<16) ends[i].yy=ends[i-1].yy+16;
  ends.forEach(e=>{g+=`<text class="lbl" data-c="${e.c}" x="${e.xx+10}" y="${e.yy+4}" font-size="13" font-weight="700" fill="${e.col}">${surname(e.c)} <tspan font-weight="500" fill="var(--muted)">${lang==="fr"?e.v.toFixed(0)+" %":e.v.toFixed(0)+"%"}</tspan></text>`});
  svg.innerHTML=g;
  const set=c=>svg.querySelectorAll(".ser,.lbl").forEach(el=>el.style.opacity=!c||el.dataset.c===c?1:.15);
  svg.querySelectorAll(".lbl").forEach(el=>{el.addEventListener("mouseenter",()=>set(el.dataset.c));el.addEventListener("click",e=>{e.stopPropagation();set(el.dataset.c)})});
  svg.addEventListener("mouseleave",()=>set(null)); svg.addEventListener("click",()=>set(null));
}
// ---- Divergence chart: polls vs markets over time, from the weekly series of data.json ------------
const DV={cand:null,tf:"ALL",pin:null,hov:null,w:0,geo:null,ro:null};
const DV_DAYS={"1M":30,"3M":91,"6M":183,ALL:1e9};
const DV_PAGE={poll:"var(--poll)",market:"var(--market)",fill:"var(--market-soft)",rule:"var(--rule)",muted:"var(--muted)",faint:"var(--faint)",ink:"var(--ink)",surface:"var(--surface)"};
const DV_LIGHT={poll:"#3446A6",market:"#0B8474",fill:"rgba(11,132,116,.18)",rule:"#DDE0E7",muted:"#5A6071",faint:"#9EA4B2",ink:"#161922",surface:"#FFFFFF"};
const dvTs=d=>Date.parse(d+"T00:00:00Z");
const xml=v=>String(v).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/"/g,"&quot;");
const dvDate=d=>{const [yy,mm,dd]=d.split("-"); return (+dd)+" "+t("months")[+mm-1]+" "+yy};
const dvSigned=d=>{const r=Math.round(d*10)/10; const a=Math.abs(r).toFixed(1); return (r>0?"+":r<0?"−":"")+(lang==="fr"?a.replace(".",","):a)+nb+"pts"};
const dvLastIdx=a=>{for(let i=a.length-1;i>=0;i--) if(a[i]!=null) return i; return -1};
const dvNote=e=>e[lang==="fr"?"noteFr":"noteEn"]||"";

function dvData(){
  const WK=DATA.weekly; if(!WK||!WK.weeks.length) return null;
  const names=Object.keys(WK.series); if(!DV.cand||!WK.series[DV.cand]) DV.cand=names[0];
  const s=WK.series[DV.cand], cut=dvTs(WK.weeks[WK.weeks.length-1])-DV_DAYS[DV.tf]*864e5;
  const a=Math.max(0,WK.weeks.findIndex(w=>dvTs(w)>=cut));
  return {names,cand:DV.cand,weeks:WK.weeks.slice(a),poll:s.poll.slice(a),market:s.market.slice(a)};
}

/** SVG markup of the chart. Pure: `col` decides page colours (CSS variables) or literal ones (PNG export). */
function dvChart(o){
  const {W,H,weeks,poll,market,col}=o, ml=40,mr=14,mt=32,mb=28, n=weeks.length;
  const t0=dvTs(weeks[0]), t1=dvTs(weeks[n-1]), span=Math.max(1,t1-t0), days=span/864e5;
  const px=tt=>ml+(tt-t0)/span*(W-ml-mr), x=i=>px(dvTs(weeks[i]));
  const vals=[...poll,...market].filter(v=>v!=null), ymax=Math.max(40,Math.ceil(Math.max(0,...vals)/10)*10);
  const y=v=>mt+(1-v/ymax)*(H-mt-mb), pctTxt=lang==="fr"?nb+"%":"%";
  let g="";
  for(let v=0;v<=ymax;v+=10) g+=`<line x1="${ml}" x2="${W-mr}" y1="${y(v)}" y2="${y(v)}" stroke="${col.rule}"/><text x="${ml-6}" y="${y(v)+4}" text-anchor="end" font-size="12" fill="${col.muted}">${v}${pctTxt}</text>`;
  const tick=(xx,label)=>`<line x1="${xx}" x2="${xx}" y1="${H-mb}" y2="${H-mb+4}" stroke="${col.faint}"/>`+(label?`<text x="${xx}" y="${H-8}" text-anchor="middle" font-size="12" fill="${col.muted}">${label}</text>`:"");
  if(days<=45) weeks.forEach((w,i)=>{const [,mm,dd]=w.split("-"); g+=tick(x(i),(+dd)+" "+t("months")[+mm-1])});
  else{ const d0=new Date(t0); for(let k=1;;k++){ const dt=new Date(Date.UTC(d0.getUTCFullYear(),d0.getUTCMonth()+k,1)); if(+dt>t1) break; const mo=dt.getUTCMonth()+1;
    g+=tick(px(+dt),(days<=240||mo%2===1)?monthLab(dt.getUTCFullYear()+"-"+String(mo).padStart(2,"0"),1):""); } }
  // the écart: for each run of weeks where both lines exist (a single missing week is bridged), the polygon between the poll line and the market line
  const P=poll.map((v,i)=>v==null||market[i]==null?null:i).filter(i=>i!=null);   // weeks where both lines exist
  for(let k=0;k<P.length;){ let e=k; while(e+1<P.length&&P[e+1]-P[e]<=2) e++;
    if(e>k){ const fwd=[],back=[]; for(let j=k;j<=e;j++) fwd.push(x(P[j]).toFixed(1)+" "+y(poll[P[j]]).toFixed(1));
      for(let i=P[e];i>=P[k];i--) if(market[i]!=null) back.push(x(i).toFixed(1)+" "+y(market[i]).toFixed(1));
      if(back.length) g+=`<path d="M${fwd.join(" L")} L${back.join(" L")} Z" fill="${col.fill}" stroke="none"/>`; }
    k=e+1; }
  const M=pathOf(market,x,y,2), Pp=pathOf(poll,x,y,1);   // one missing market week is bridged; the poll line breaks wherever no poll fell in the 30 days before a week
  g+=`<path d="${M.d}" fill="none" stroke="${col.market}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/><path d="${Pp.d}" fill="none" stroke="${col.poll}" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>`;
  if(M.last!=null){ const cx=x(M.last), cy=y(market[M.last]); g+=`<rect x="${cx-4.5}" y="${cy-4.5}" width="9" height="9" rx="1.5" transform="rotate(45 ${cx} ${cy})" fill="${col.market}" stroke="${col.surface}" stroke-width="1.5"/>`; }
  poll.forEach((v,i)=>{ if(v!=null&&(i===Pp.last||poll[i-1]==null&&poll[i+1]==null)) g+=`<circle cx="${x(i)}" cy="${y(v)}" r="${i===Pp.last?4.5:2.8}" fill="${col.poll}" stroke="${col.surface}" stroke-width="1.5"/>`});
  if(o.interactive) g+=`<line id="dvGuide" y1="${mt}" y2="${H-mb}" stroke="${col.ink}" stroke-opacity=".35" visibility="hidden"/><g id="dvDots"></g>`;
  (o.events||[]).forEach((e,i)=>{ const tt=dvTs(e.date); if(tt<t0||tt>t1) return; const xx=px(tt), cy=mt-16;
    g+=`<line x1="${xx}" x2="${xx}" y1="${cy+9}" y2="${H-mb}" stroke="${col.faint}" stroke-dasharray="2 3"/>`+
      `<g class="evm" data-e="${i}"${o.interactive?` role="button" tabindex="0" aria-label="${xml(e[lang])}" aria-pressed="false"`:""}><circle cx="${xx}" cy="${cy}" r="15" fill="transparent" stroke="none"/><circle cx="${xx}" cy="${cy}" r="9.5" fill="${col.surface}" stroke="${col.faint}" stroke-width="1.5"/><text x="${xx}" y="${cy+4}" text-anchor="middle" font-size="11" font-weight="700" fill="${col.ink}">${i+1}</text></g>`; });
  return {svg:g, geo:{W,H,ml,mr,mt,mb,x,y,n}};
}

function dvSummary(D){
  const im=dvLastIdx(D.market), ip=dvLastIdx(D.poll);
  let ib=D.weeks.length-1; while(ib>=0&&(D.market[ib]==null||D.poll[ib]==null)) ib--;   // the gap compares the two lines in the same week
  return {im,ip,m:im<0?null:D.market[im],p:ip<0?null:D.poll[ip],mw:im<0?"":D.weeks[im],pw:ip<0?"":D.weeks[ip],gap:ib<0?null:D.market[ib]-D.poll[ib]};
}

function dvReadout(idx){
  const G=DV.geo, D=G&&G.D; if(!D) return; const guide=document.getElementById("dvGuide"), dots=document.getElementById("dvDots"), out=document.getElementById("dvReadout");
  if(idx==null){ if(guide){guide.setAttribute("visibility","hidden"); dots.innerHTML="";}
    const S=dvSummary(D); out.innerHTML=S.m==null||S.p==null?"":tf("dvLast",{m:pct1(S.m),mw:dvDate(S.mw),p:pct1(S.p),pw:dvDate(S.pw)}); return; }
  const m=D.market[idx], p=D.poll[idx], xx=G.x(idx);
  guide.setAttribute("x1",xx); guide.setAttribute("x2",xx); guide.setAttribute("visibility","visible");
  dots.innerHTML=(m!=null?`<circle cx="${xx}" cy="${G.y(m)}" r="5" fill="var(--market)" stroke="var(--surface)" stroke-width="2"/>`:"")+(p!=null?`<circle cx="${xx}" cy="${G.y(p)}" r="5" fill="var(--poll)" stroke="var(--surface)" stroke-width="2"/>`:"");
  out.innerHTML=tf("dvAt",{w:dvDate(D.weeks[idx]),m:m==null?"–":pct1(m),p:p==null?t("dvNoPoll"):pct1(p),g:m!=null&&p!=null?dvSigned(m-p):"–"});
}

/** Marker and chip highlight + note panel: hovered event first, else the pinned one. No redraw, so keyboard focus survives. */
function dvSync(){
  const i=DV.hov!=null?DV.hov:DV.pin!=null?DV.pin:EVENTS.length-1, e=i>=0?EVENTS[i]:null;
  document.querySelectorAll("#dvChart .evm").forEach(gm=>{const on=+gm.dataset.e===i; gm.classList.toggle("on",on); gm.setAttribute("aria-pressed",String(+gm.dataset.e===DV.pin))});
  document.querySelectorAll("#dvEvents button").forEach(b=>{const k=+b.dataset.e; b.classList.toggle("on",k===i); b.setAttribute("aria-pressed",String(k===DV.pin))});
  document.getElementById("dvNote").innerHTML=e?`<strong>${xml(e[lang])}</strong><span class="d">${dvDate(e.date)}</span><p>${xml(dvNote(e))}</p>`:`<span style="color:var(--muted)">${t("dvHint")}</span>`;
}
function dvToggleEvent(i){ DV.pin=DV.pin===i?null:i; dvSync(); }

function dvDrawChart(){
  const box=document.getElementById("dvChart"), D=dvData(); if(!D) return;
  const W=Math.max(280,Math.round(box.clientWidth)||640), H=W<520?250:340; DV.w=Math.round(box.clientWidth);
  const C=dvChart({W,H,weeks:D.weeks,poll:D.poll,market:D.market,events:EVENTS,col:DV_PAGE,interactive:true});
  box.setAttribute("aria-label",tf("dvAria",{n:D.cand}));
  box.innerHTML=`<svg id="dvSvg" viewBox="0 0 ${W} ${H}" role="presentation">${C.svg}</svg>`;
  DV.geo={...C.geo,D};
  const svg=document.getElementById("dvSvg");
  const near=e=>{const r=svg.getBoundingClientRect(), px=(e.clientX-r.left)/r.width*W; let b=0; for(let i=1;i<D.weeks.length;i++) if(Math.abs(C.geo.x(i)-px)<Math.abs(C.geo.x(b)-px)) b=i; return b};
  svg.addEventListener("pointermove",e=>dvReadout(near(e)));
  svg.addEventListener("pointerdown",e=>dvReadout(near(e)));
  svg.addEventListener("pointerleave",e=>{ if(e.pointerType==="mouse") dvReadout(null) });
  svg.querySelectorAll(".evm").forEach(gm=>{ const i=+gm.dataset.e;
    gm.addEventListener("pointerenter",e=>{ if(e.pointerType==="mouse"){DV.hov=i;dvSync()} });
    gm.addEventListener("pointerleave",e=>{ if(e.pointerType==="mouse"){DV.hov=null;dvSync()} });
    gm.addEventListener("focus",()=>{ if(gm.matches(":focus-visible")){DV.hov=i;dvSync()} }); gm.addEventListener("blur",()=>{DV.hov=null;dvSync()});   // keyboard focus previews; a mouse or touch click must not leave a sticky hover
    gm.addEventListener("click",e=>{e.stopPropagation();dvToggleEvent(i)});
    gm.addEventListener("keydown",e=>{ if(e.key==="Enter"||e.key===" "){e.preventDefault();dvToggleEvent(i)} }); });
  dvReadout(null); dvSync();
}

function renderDv(){
  const sec=document.getElementById("multiSection"), D=dvData();
  if(!D){ sec.hidden=true; return } sec.hidden=false;
  const S=dvSummary(D), gap=S.gap;
  document.getElementById("dvName").textContent=D.cand;
  const pill=document.getElementById("dvPill"); pill.hidden=gap==null; if(gap!=null){ pill.textContent=t("gapCol")+" "+dvSigned(gap); pill.classList.toggle("neg",gap<0) }
  const pills=document.getElementById("dvPills"); pills.setAttribute("aria-label",t("dvCand"));
  pills.innerHTML=D.names.map(n=>`<button type="button" data-c="${xml(n)}" aria-pressed="${n===D.cand}">${xml(surname(n))}</button>`).join("");
  pills.querySelectorAll("button").forEach(b=>b.addEventListener("click",()=>{DV.cand=b.dataset.c;renderDv()}));
  const tf=document.getElementById("dvTf"); tf.setAttribute("aria-label",t("dvPeriod"));
  tf.querySelectorAll("button").forEach(b=>{ b.setAttribute("aria-pressed",String(b.dataset.tf===DV.tf)); b.onclick=()=>{DV.tf=b.dataset.tf;renderDv()}; });
  document.getElementById("dvLegend").innerHTML=
    `<li><svg width="26" height="10" aria-hidden="true"><line x1="1" x2="25" y1="5" y2="5" stroke="var(--market)" stroke-width="2.5" stroke-linecap="round"/></svg>${t("dvLegM")}</li>`+
    `<li><svg width="26" height="10" aria-hidden="true"><line x1="1" x2="25" y1="5" y2="5" stroke="var(--poll)" stroke-width="2.5" stroke-linecap="round"/><circle cx="13" cy="5" r="3" fill="var(--poll)"/></svg>${t("dvLegP")}</li>`+
    `<li><span class="tint" aria-hidden="true"></span>${t("dvLegG")}</li>`;
  const ev=document.getElementById("dvEvents"); ev.setAttribute("aria-label",t("evList")); ev.hidden=!EVENTS.length; document.getElementById("dvNote").hidden=!EVENTS.length;
  ev.innerHTML=EVENTS.map((e,i)=>`<li><button type="button" data-e="${i}" aria-pressed="false"><b>${i+1}</b>${xml(e[lang])}</button></li>`).join("");
  ev.querySelectorAll("button").forEach(b=>{ const i=+b.dataset.e; b.addEventListener("click",()=>dvToggleEvent(i));
    b.addEventListener("pointerenter",e=>{ if(e.pointerType==="mouse"){DV.hov=i;dvSync()} }); b.addEventListener("pointerleave",e=>{ if(e.pointerType==="mouse"){DV.hov=null;dvSync()} }); });
  dvDrawChart();
  const box=document.getElementById("dvChart");
  if(!DV.ro&&window.ResizeObserver){ DV.ro=new ResizeObserver(()=>{ const w=Math.round(box.clientWidth); if(w&&Math.abs(w-DV.w)>2) dvDrawChart() }); DV.ro.observe(box); }
}

// Press export: one self-contained SVG card (fonts embedded, literal light colours), rasterised at 2x.
let DV_FONTS=null;
async function dvFonts(){
  if(DV_FONTS) return DV_FONTS;
  const b64=async u=>{ const r=await fetch(u); if(!r.ok) throw new Error(u); const by=new Uint8Array(await r.arrayBuffer()); let s=""; for(let i=0;i<by.length;i+=0x8000) s+=String.fromCharCode.apply(null,by.subarray(i,i+0x8000)); return btoa(s) };
  return DV_FONTS={sans:await b64("fonts/schibsted-grotesk-latin.woff2"),serif:await b64("fonts/spectral-500-latin.woff2")};
}
async function dvExport(){
  const D=dvData(), btn=document.getElementById("dvExport"), msg=document.getElementById("dvExpMsg"); if(!D||btn.disabled) return;
  btn.disabled=true; msg.textContent="";
  try{
    let F=null; try{ F=await dvFonts() }catch(e){}
    const W=1200,H=675,S=2,pad=48,cw=W-2*pad,ch=316,C=DV_LIGHT, Z=dvSummary(D), gap=Z.gap;
    const face=F?`<style>@font-face{font-family:"Schibsted Grotesk";font-weight:400 900;src:url(data:font/woff2;base64,${F.sans}) format("woff2")}@font-face{font-family:"Spectral";font-weight:500;src:url(data:font/woff2;base64,${F.serif}) format("woff2")}</style>`:"";
    const chart=dvChart({W:cw-24,H:ch,weeks:D.weeks,poll:D.poll,market:D.market,events:EVENTS,col:C,interactive:false}).svg;
    const cardY=176, legY=cardY+ch+24+30, shown=EVENTS.map((e,i)=>({e,i})).filter(({e})=>{const tt=dvTs(e.date); return tt>=dvTs(D.weeks[0])&&tt<=dvTs(D.weeks[D.weeks.length-1])});
    let pillSvg=""; if(gap!=null){ const txt=xml(t("gapCol")+" "+dvSigned(gap)), w=txt.length*9.6+30, neg=gap<0;
      pillSvg=`<rect x="${W-pad-w}" y="92" width="${w}" height="36" rx="18" fill="${neg?"rgba(52,70,166,.16)":C.fill}"/><text x="${W-pad-w/2}" y="116" text-anchor="middle" font-size="18" font-weight="700" fill="${neg?C.poll:C.market}">${txt}</text>`; }
    const legend=`<line x1="${pad}" x2="${pad+26}" y1="${legY-4}" y2="${legY-4}" stroke="${C.market}" stroke-width="2.5" stroke-linecap="round"/><text x="${pad+34}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegM"))}</text>`+
      `<line x1="${pad+300}" x2="${pad+326}" y1="${legY-4}" y2="${legY-4}" stroke="${C.poll}" stroke-width="2.5" stroke-linecap="round"/><circle cx="${pad+313}" cy="${legY-4}" r="3" fill="${C.poll}"/><text x="${pad+334}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegP"))}</text>`+
      `<rect x="${pad+640}" y="${legY-13}" width="22" height="11" rx="3" fill="${C.fill}" stroke="${C.market}"/><text x="${pad+670}" y="${legY}" font-size="13" fill="${C.muted}">${xml(t("dvLegG"))}</text>`;
    const evs=shown.length?`<text x="${pad}" y="${legY+26}" font-size="13" fill="${C.muted}">${xml(t("dvEv"))}${lang==="fr"?nb+": ":": "}${shown.map(({e,i})=>(i+1)+". "+xml(e[lang])).join("   ")}</text>`:"";
    const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" font-family="'Schibsted Grotesk',Helvetica,Arial,sans-serif">${face}`+
      `<rect width="${W}" height="${H}" fill="#EEF0F4"/>`+
      `<circle cx="${pad+6}" cy="${pad+6}" r="6" fill="${C.poll}"/><rect x="${pad+21}" y="${pad}" width="12" height="12" rx="2" fill="${C.market}" transform="rotate(45 ${pad+27} ${pad+6})"/><text x="${pad+44}" y="${pad+12}" font-size="17" font-weight="800" fill="${C.ink}">L'Écart · ${xml(t("ctx"))}</text>`+
      `<text x="${pad}" y="120" font-family="Spectral,Georgia,serif" font-size="46" font-weight="500" fill="${C.ink}">${xml(D.cand)}</text>${pillSvg}`+
      `<text x="${pad}" y="152" font-size="16" fill="${C.muted}">${xml(t("dvCap"))}</text>`+
      `<rect x="${pad}" y="${cardY}" width="${cw}" height="${ch+24}" rx="16" fill="${C.surface}" stroke="${C.rule}"/><g transform="translate(${pad+12} ${cardY+12})">${chart}</g>`+
      `${legend}${evs}`+
      `<line x1="${pad}" x2="${W-pad}" y1="${H-62}" y2="${H-62}" stroke="${C.rule}"/>`+
      `<text x="${pad}" y="${H-38}" font-size="12.5" fill="${C.muted}">${xml(t("dvSrc"))} ${xml(t("dvAsOf"))} ${dvDate(DATA.updated)}.</text>`+
      `<text x="${W-pad}" y="${H-38}" text-anchor="end" font-size="12.5" fill="${C.muted}">lukesegault.github.io/lecart</text></svg>`;
    const img=new Image(); img.src="data:image/svg+xml;charset=utf-8,"+encodeURIComponent(svg); await img.decode();
    await new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)));   // let the embedded fonts settle before drawing
    const cv=document.createElement("canvas"); cv.width=W*S; cv.height=H*S; cv.getContext("2d").drawImage(img,0,0,W*S,H*S);
    const blob=await new Promise(r=>cv.toBlob(r,"image/png")); if(!blob) throw new Error("toBlob");
    const a=document.createElement("a"), slug=surname(D.cand).normalize("NFD").replace(/[̀-ͯ]/g,"").toLowerCase().replace(/[^a-z0-9]+/g,"-");
    a.href=URL.createObjectURL(blob); a.download=`lecart-${slug}-${DATA.updated}.png`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(()=>URL.revokeObjectURL(a.href),4000);
  }catch(e){ msg.textContent=t("dvExpFail") } finally{ btn.disabled=false }
}
document.getElementById("dvExport").addEventListener("click",dvExport);

function table(){
  const d=s=>{const [y,m,dd]=s.split("-");return dd+"/"+m};
  document.querySelector("#polltable tbody").innerHTML=DATA.polls.slice().reverse().map(p=>{
    const f=v=>v==null?"–":(lang==="fr"?String(v).replace(".",","):v);
    return `<tr><td>${p.inst}</td><td>${p.for}</td><td>${d(p.start)} ${t("to")} ${d(p.end)}/${p.end.slice(0,4)}</td><td>${p.n.toLocaleString(lang==="fr"?"fr-FR":"en-GB")}</td><td>${f(p.v["Marine Le Pen"])}</td><td>${f(p.v["Édouard Philippe"])}</td><td>${f(p.v["Jean-Luc Mélenchon"])}</td></tr>`}).join("");
}
// A discreet notice when the daily refresh has not run for more than two days.
function renderStale(){
  let el=document.getElementById("stale");
  if(!((Date.now()-Date.parse(DATA.updated+"T00:00:00Z"))/864e5>2)){ if(el) el.remove(); return }
  if(!el){ el=document.createElement("p"); el.id="stale"; el.className="meta stale"; el.setAttribute("role","status"); document.querySelector(".stamp").after(el) }
  el.textContent=t("stale");
}
function renderAll(first){ applyStatic(); renderSpot(first); renderBoard(); trend(); renderDv(); table(); renderOpt(); renderStale(); }

// Aggregated GoatCounter event (cookie-free). No-op after opt-out, or if count.js has not loaded yet or is blocked.
const track=name=>{ try{ if(window.lecartOptOut.get()) return; window.goatcounter.count({path:name,title:name,event:true}) }catch(e){} };
const optEl=document.getElementById("optOut"), optMsg=document.getElementById("optMsg");
const renderOpt=()=>{ optEl.textContent=t(window.lecartOptOut&&window.lecartOptOut.get()?"optIn":"optOut") };
optEl.addEventListener("click",e=>{ e.preventDefault(); const O=window.lecartOptOut; if(!O) return; const ok=O.set(!O.get()); optMsg.textContent=ok?"":" "+t("optFail"); renderOpt() });
document.querySelectorAll("[data-lang]").forEach(b=>b.addEventListener("click",()=>{track("lang-"+b.dataset.lang);lang=b.dataset.lang;try{localStorage.setItem("lecart-lang",lang)}catch(e){} renderAll(false)}));
document.querySelectorAll("[data-q]").forEach(b=>b.addEventListener("click",()=>{track("q-"+b.dataset.q);state.q=b.dataset.q;document.querySelectorAll("[data-q]").forEach(x=>x.setAttribute("aria-pressed",x===b));renderBoard()}));
document.querySelectorAll("[data-u]").forEach(b=>b.addEventListener("click",()=>{track("u-"+b.dataset.u);state.u=b.dataset.u;document.querySelectorAll("[data-u]").forEach(x=>x.setAttribute("aria-pressed",x===b));renderBoard()}));
document.getElementById("more").addEventListener("click",()=>{state.all=!state.all;renderBoard()});
const bar=document.querySelector(".bar-top"), menuBtn=document.getElementById("menuBtn");
const setMenu=open=>{ bar.classList.toggle("open",open); menuBtn.setAttribute("aria-expanded",String(open)) };
menuBtn.addEventListener("click",e=>{ e.stopPropagation(); setMenu(!bar.classList.contains("open")) });
document.querySelectorAll("#nav a").forEach(a=>a.addEventListener("click",()=>setMenu(false)));
document.addEventListener("click",e=>{ if(!bar.contains(e.target)) setMenu(false) });
document.addEventListener("keydown",e=>{ if(e.key==="Escape"&&bar.classList.contains("open")){ setMenu(false); menuBtn.focus() } });
window.matchMedia("(min-width:641px)").addEventListener("change",e=>{ if(e.matches) setMenu(false) });
renderAll(true);

})();
