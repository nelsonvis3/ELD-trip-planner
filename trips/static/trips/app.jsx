function haversineMiles([lon1, lat1], [lon2, lat2]) {
  const R = 3958.8, rad = Math.PI / 180;
  const dLat = (lat2 - lat1) * rad, dLon = (lon2 - lon1) * rad;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(a));
}

function makePointFinder(coords, routeMiles) {
  const cum = [0];
  for (let i = 1; i < coords.length; i++) {
    cum.push(cum[i - 1] + haversineMiles(coords[i - 1], coords[i]));
  }
  const scale = cum[cum.length - 1] / routeMiles;
  return (miles) => {
    const target = Math.min(Math.max(miles * scale, 0), cum[cum.length - 1]);
    let i = 1;
    while (i < cum.length - 1 && cum[i] < target) i++;
    const t = (target - cum[i - 1]) / (cum[i] - cum[i - 1] || 1);
    return [
      coords[i - 1][0] + (coords[i][0] - coords[i - 1][0]) * t,
      coords[i - 1][1] + (coords[i][1] - coords[i - 1][1]) * t,
    ];
  };
}

function popupContent(title, detail) {
  const div = document.createElement("div");
  const b = document.createElement("strong");
  b.textContent = title;
  div.append(b, document.createElement("br"), document.createTextNode(detail));
  return div;
}

function drawTrip(map, data) {
  const run = () => {
    const coords = data.route.geometry.coordinates;

    (map._tripMarkers || []).forEach((m) => m.remove());
    map._tripMarkers = [];

    const feature = { type: "Feature", geometry: data.route.geometry };
    if (map.getSource("route")) {
      map.getSource("route").setData(feature);
    } else {
      map.addSource("route", { type: "geojson", data: feature });
      map.addLayer({
        id: "route-casing", type: "line", source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#ffffff", "line-width": 9 },
      });
      map.addLayer({
        id: "route-line", type: "line", source: "route",
        layout: { "line-join": "round", "line-cap": "round" },
        paint: { "line-color": "#2563eb", "line-width": 5 },
      });
    }

    const names = ["Ubicación actual", "Pickup", "Drop-off"];
    const colors = ["#16a34a", "#f59e0b", "#dc2626"];
    data.route.places.forEach((p, i) => {
      const marker = new maplibregl.Marker({ color: colors[i] })
        .setLngLat([p.lon, p.lat])
        .setPopup(new maplibregl.Popup().setDOMContent(popupContent(names[i], p.name)))
        .addTo(map);
      map._tripMarkers.push(marker);
    });

    const pointAt = makePointFinder(coords, data.distance_miles);
    data.events
      .filter((e) => e.type !== "driving" && !/Pickup|Drop-off/.test(e.label))
      .forEach((e) => {
        const el = document.createElement("div");
        el.style.cssText =
          "width:14px;height:14px;border-radius:50%;border:2px solid #fff;" +
          "box-shadow:0 0 0 1px rgba(0,0,0,.3);background:" +
          (e.type === "offduty" ? "#6b7280" : "#f59e0b");
        const when = new Date(e.start).toLocaleString();
        const marker = new maplibregl.Marker({ element: el })
          .setLngLat(pointAt(e.cumulative_miles))
          .setPopup(new maplibregl.Popup().setDOMContent(
            popupContent(e.label, `Milla ${e.cumulative_miles} · ${when} · ${e.minutes} min`)
          ))
          .addTo(map);
        map._tripMarkers.push(marker);
      });

    const bounds = coords.reduce(
      (b, c) => b.extend(c),
      new maplibregl.LngLatBounds(coords[0], coords[0])
    );
    map.fitBounds(bounds, { padding: 60 });
  };

  if (map.isStyleLoaded()) run();
  else map.once("idle", run);
}
const {useEffect,useRef,useState}=React;
const STATUS_Y={offduty:18,sleeper:43,driving:68,onduty:93};
const ZONES=['America/New_York','America/Chicago','America/Denver','America/Phoenix','America/Los_Angeles','America/Anchorage','Pacific/Honolulu'];
const browserZone=Intl.DateTimeFormat().resolvedOptions().timeZone||'America/Chicago';
function standardOffsetMinutes(zone,year){const instant=Date.UTC(year,0,15,12),p=new Intl.DateTimeFormat('en-US',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(instant)).reduce((o,x)=>(o[x.type]=x.value,o),{});return (Date.UTC(Number(p.year),Number(p.month)-1,Number(p.day),Number(p.hour),Number(p.minute))-instant)/60000}
function localInputValue(date,zone){const standard=new Date(date.getTime()+standardOffsetMinutes(zone,date.getFullYear())*60000),p=[standard.getUTCFullYear(),String(standard.getUTCMonth()+1).padStart(2,'0'),String(standard.getUTCDate()).padStart(2,'0'),String(standard.getUTCHours()).padStart(2,'0'),String(standard.getUTCMinutes()).padStart(2,'0')];return `${p[0]}-${p[1]}-${p[2]}T${p[3]}:${p[4]}`}
function fmtShortDate(iso){const date=String(iso).slice(0,10),parsed=new Date(`${date}T12:00:00Z`);return Number.isNaN(parsed.getTime())?date:new Intl.DateTimeFormat(undefined,{month:'short',day:'numeric',timeZone:'UTC'}).format(parsed)}
function fmtTime(iso){const match=String(iso).match(/T(\d{2}):(\d{2})/);if(!match)return '—';const hour=Number(match[1]),minute=match[2];return `${hour%12||12}:${minute} ${hour<12?'AM':'PM'}`}
function fmtDate(iso){const date=String(iso).slice(0,10);const parsed=new Date(`${date}T12:00:00Z`);return Number.isNaN(parsed.getTime())?date:new Intl.DateTimeFormat(undefined,{weekday:'long',month:'long',day:'numeric',year:'numeric',timeZone:'UTC'}).format(parsed)}
function duration(minutes){const h=Math.floor(minutes/60),m=minutes%60;return h?`${h}h ${String(m).padStart(2,'0')}m`:`${m} min`}
function pointOnRoute(line,miles,totalMiles){const dist=[];let sum=0;dist.push(sum);for(let i=1;i<line.length;i++){const a=line[i-1],b=line[i],r=Math.PI/180,lat1=a[1]*r,lat2=b[1]*r,dl=(b[0]-a[0])*r,dp=lat2-lat1,h=Math.sin(dp/2)**2+Math.cos(lat1)*Math.cos(lat2)*Math.sin(dl/2)**2;sum+=3958.8*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h));dist.push(sum)}const target=Math.max(0,Math.min(sum,miles/totalMiles*sum));let i=1;while(i<dist.length-1&&dist[i]<target)i++;const t=(target-dist[i-1])/(dist[i]-dist[i-1]||1);return [line[i-1][1]+(line[i][1]-line[i-1][1])*t,line[i-1][0]+(line[i][0]-line[i-1][0])*t]}
function App(){
 const mapRef=useRef(null),map=useRef(null),routeLayer=useRef(null),markerLayer=useRef(null);
 const initialZone=ZONES.includes(browserZone)?browserZone:'America/Chicago';
 const[form,setForm]=useState({current_location:'',pickup_location:'',dropoff_location:'',cycle_used:'0',time_zone:initialZone,departure:localInputValue(new Date(),initialZone)});
 const[loading,setLoading]=useState(false),[error,setError]=useState(''),[plan,setPlan]=useState(null),[mapError,setMapError]=useState(false);
 useEffect(()=>{if(!map.current&&mapRef.current){map.current=new maplibregl.Map({container:mapRef.current,style:'https://tiles.openfreemap.org/styles/positron',center:[-98.35,39.5],zoom:4,attributionControl:true});map.current.addControl(new maplibregl.NavigationControl({showCompass:false}),'bottom-right');map.current.on('error',()=>setMapError(true));markerLayer.current=[];routeLayer.current=()=>{if(map.current.getLayer('trip-route'))map.current.removeLayer('trip-route');if(map.current.getSource('trip-route'))map.current.removeSource('trip-route');markerLayer.current?.forEach(marker=>marker.remove());markerLayer.current=[]}}},[]);
 function change(e){const{name,value}=e.target;setForm({...form,[name]:value})}
 async function submit(e){
  e.preventDefault();setError('');setPlan(null);routeLayer.current?.();setLoading(true);
  try{
   if(!form.current_location.trim()||!form.pickup_location.trim()||!form.dropoff_location.trim())throw new Error('Enter a current location, pickup and drop-off.');
   const cycle=Number(form.cycle_used);
   if(!Number.isFinite(cycle)||cycle<0||cycle>70)throw new Error('Cycle used must be from 0 through 70 hours.');
   if(!form.cycle_used.trim())throw new Error('Enter the current cycle hours used.');
   if(!form.departure)throw new Error('Choose a valid departure time.');
   const response=await fetch('/api/plan/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':document.cookie.match(/csrftoken=([^;]+)/)?.[1]||''},body:JSON.stringify({...form,cycle_used:cycle})});
   const responseText=await response.text();let result;
   try{result=JSON.parse(responseText)}catch{const detail=responseText.replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim().slice(0,180);throw new Error(`Planner returned HTTP ${response.status}${detail?`: ${detail}`:'. Please try again.'}`)}
   if(!response.ok)throw new Error(result.error||`Planner returned HTTP ${response.status}.`);
   if(!result.route?.geometry?.coordinates?.length||!result.days?.length)throw new Error('Planner returned an incomplete result. Please try again.');
   setPlan(result);
   try{
    const route=result.route,line=route.geometry.coordinates;
    const draw=()=>{try{if(!map.current?.isStyleLoaded())return;routeLayer.current?.();map.current.addSource('trip-route',{type:'geojson',data:route.geometry});map.current.addLayer({id:'trip-route',type:'line',source:'trip-route',layout:{'line-join':'round','line-cap':'round'},paint:{'line-color':'#1769aa','line-width':5,'line-opacity':.9}});const palette=['#1769aa','#16834b','#d33f49'],labels=['Current location','Pickup','Drop-off'];route.places.forEach((p,i)=>{const element=document.createElement('div');element.className='map-point';element.style.background=palette[i];const popup=document.createElement('div'),title=document.createElement('strong'),text=document.createElement('div');title.textContent=labels[i];text.textContent=p.name;popup.append(title,text);markerLayer.current.push(new maplibregl.Marker({element,anchor:'center'}).setLngLat([p.lon,p.lat]).setPopup(new maplibregl.Popup({offset:14}).setDOMContent(popup)).addTo(map.current))});result.events.filter(ev=>ev.type==='offduty'||ev.label.startsWith('Fuel stop')||ev.label==='30-minute break').forEach(ev=>{const at=pointOnRoute(line,ev.start_miles??ev.cumulative_miles,route.distance_miles),element=document.createElement('div'),isRest=ev.type==='offduty'||ev.label==='30-minute break';element.className=`stop-icon ${isRest?'rest':'fuel'}`;element.textContent=isRest?'R':'F';const popup=document.createElement('div'),title=document.createElement('strong'),text=document.createElement('div');title.textContent=ev.label;text.textContent=`${fmtTime(ev.start)} · ${duration(ev.minutes)} · ${Math.round(ev.start_miles??ev.cumulative_miles)} route mi`;popup.append(title,text);markerLayer.current.push(new maplibregl.Marker({element,anchor:'center'}).setLngLat([at[1],at[0]]).setPopup(new maplibregl.Popup({offset:14}).setDOMContent(popup)).addTo(map.current))});const bounds=line.reduce((b,p)=>b.extend(p),new maplibregl.LngLatBounds(line[0],line[0]));map.current.fitBounds(bounds,{padding:48})}catch{setMapError(true)}};
    if(!map.current)throw new Error('Map initialization failed.');
    if(map.current.isStyleLoaded())draw();else map.current.once('load',draw);
   }catch{setMapError(true)}
  }catch(err){setError(err.message||'Something went wrong while planning this trip.')}finally{setLoading(false)}
 }
 const route=plan?.route;
 return <div className="shell"><header className="topbar no-print"><a className="brand" href="#top"><span className="brand-icon">RL</span><span>Roadledger</span></a><div className="top-meta"><span className="live-dot"/>TRIP OPERATIONS <i/> PROPERTY CARRIER · 70 / 8</div><button className="print-button" disabled={!plan} onClick={()=>window.print()}>Print daily logs <b>⌘ P</b></button></header>
  <main id="top"><section className="hero"><div><div className="kicker">HOURS OF SERVICE · TRIP PLANNER</div><h1>Plan the miles.<br/><span>Know the hours.</span></h1><p>A route and daily duty record shaped around your available hours.</p></div><div className="hero-note"><span>01—04</span><p>ROUTE<br/>STOPS<br/>DUTY LOGS</p></div></section>
  <div className="workspace"><aside className="inputs no-print"><div className="section-cap"><span>TRIP INPUT</span><span>01 / 03</span></div><form onSubmit={submit}><AddressField label="Current location" color="blue" name="current_location" value={form.current_location} onChange={change} placeholder="City, state or address"/><AddressField label="Pickup location" color="green" name="pickup_location" value={form.pickup_location} onChange={change} placeholder="City, state or address"/><AddressField label="Drop-off location" color="red" name="dropoff_location" value={form.dropoff_location} onChange={change} placeholder="City, state or address"/><div className="input-pair"><label>Cycle used <small>HOURS</small><input name="cycle_used" type="number" required min="0" max="70" step="0.1" value={form.cycle_used} onChange={change}/></label><label>Depart at · standard time<input name="departure" type="datetime-local" required value={form.departure} onChange={change}/></label></div><p className="service-note">Locations are geocoded with Photon using OpenStreetMap data.</p>{error&&<div className="error" role="alert">{error}</div>}<button className="plan-button" disabled={loading}>{loading?<><span className="spinner"/>Building route & logs…</>:<>Generate trip plan <span>↗</span></>}</button></form><div className="rule-card"><b>Planning assumptions</b><p>Property carrier · 70 hours / 8 days · no adverse conditions · 55 mph estimated truck pace.</p><label className="zone-label">Log time zone · home terminal<select name="time_zone" value={form.time_zone} onChange={change}>{ZONES.map(zone=><option value={zone} key={zone}>{zone.replaceAll('_',' ')} · {new Intl.DateTimeFormat('en-US',{timeZone:zone,timeZoneName:'short'}).format(new Date(Date.UTC(new Date().getFullYear(),0,15,12))).split(' ').pop()}</option>)}</select></label><small className="zone-hint">Departure and every sheet use the terminal’s standard-time offset (no daylight shift).</small></div></aside>
   <div className="content">{loading&&<div className="loading-banner">Looking up the three locations, routing the trip and drawing the daily logs…</div>}
    <section className="map-card"><div className="map-heading"><div><div className="section-cap"><span>ROUTE MAP</span><span>02 / 03</span></div><h2>{route?`${Math.round(route.distance_miles).toLocaleString()} mi`:'The road ahead'}</h2></div><span className="map-stamp">OPENFREEMAP · OSRM</span></div><div id="map" ref={mapRef}/>{mapError&&<p className="map-error" role="status">Map service unavailable. Your route and stops remain available; check your connection and reload.</p>}<div className="map-legend"><Legend color="blue" label="Current"/><Legend color="green" label="Pickup"/><Legend color="red" label="Drop-off"/><Legend color="purple" label="Rest"/><Legend color="amber" label="Fuel"/></div></section>
    {!plan?<section className="empty-state"><div className="empty-symbol">24</div><div><b>Your daily logs start here.</b><span>Add the three locations and available cycle hours to build a planned route.</span></div></section>:<><section className="summary"><div className="summary-heading"><div className="section-cap"><span>TRIP SUMMARY</span><span>03 / 03</span></div><span className="arrival">ARRIVE&nbsp; {fmtDate(plan.arrival)} · {fmtTime(plan.arrival)} · {plan.standard_time_label}</span></div><div className="summary-grid"><SummaryItem label="ROUTE MILES" value={Math.round(route.distance_miles).toLocaleString()} suffix="mi"/><SummaryItem label="EST. DRIVING" value={plan.estimated_drive_hours} suffix="hrs"/><SummaryItem label="DAILY LOGS" value={plan.days.length} suffix="sheets"/><SummaryItem label="CYCLE LEFT" value={plan.cycle_hours_remaining} suffix="hrs"/></div></section>
     <section className="stops-section"><div className="section-cap"><span>STOPS & DEPARTURE</span><span>{plan.events.length} ENTRIES</span></div><div className="event-list">{plan.events.map((ev,i)=><div className="event" key={i}><time>{fmtTime(ev.start)}</time><span className={'event-mark '+(ev.type==='driving'?'drive':ev.type==='offduty'?'rest':'work')}/><div><b>{ev.label}</b><small>{ev.type==='driving'?`${ev.distance_miles} miles · `:''}{duration(ev.minutes)}</small></div><span className="event-date">{fmtShortDate(ev.start)}</span></div>)}</div></section>
     <section className="logs-section"><div className="section-cap"><span>DRIVER’S DAILY LOGS</span><span>{plan.days.length} CALENDAR {plan.days.length===1?'DAY':'DAYS'}</span></div>{plan.days.map(day=><DailyLog key={day.date} day={day} route={route}/>)}</section>
     <section className="directions-section no-print"><div className="section-cap"><span>ROUTE INSTRUCTIONS</span><span>OSRM · CAR PROFILE</span></div><div className="directions">{route.directions.map((d,i)=><div key={i}><span>{String(i+1).padStart(2,'0')}</span><b>{d.text}</b><small>{d.distance_miles?`${d.distance_miles} mi`:''}</small></div>)}</div></section>
     <p className="limitations">Planning estimate only; not an ELD record or compliance determination. A qualifying 10-hour off-duty period before departure is assumed, not included in these sheets. The selected terminal’s standard-time offset is used across every log; the logs do not switch clocks as the truck crosses zones. Truck restrictions, traffic, parking, sleeper-berth splits and prior daily duty history beyond the supplied cycle-hours figure are not modeled. Fuel stop duration is set to 30 minutes for this estimate.</p></>}
   </div></div></main><footer className="footer no-print"><span>ROADLEDGER · DRIVER WORKSPACE</span><span>© OpenStreetMap contributors · Routing by OSRM</span></footer>
 </div>
}
function AddressField({label,color,name,value,onChange,placeholder}){return <label className="address-field"><span className={'field-dot '+color}/><span className="field-label">{label}</span><input name={name} value={value} onChange={onChange} placeholder={placeholder} maxLength={180} required/></label>}
function Legend({color,label}){return <span className="legend-item"><i className={color}/>{label}</span>}
function SummaryItem({label,value,suffix}){return <div><span>{label}</span><b>{value}<small> {suffix}</small></b></div>}
function DailyLog({day,route}){const routeMiles=day.drive_miles;const from=day.from_miles<0.1?route.places[0].name:`Approx. route position · ${Math.round(day.from_miles)} mi`;const to=day.to_miles>=route.distance_miles-0.1?route.places[2].name:`Approx. route position · ${Math.round(day.to_miles)} mi`;const path=day.segments.map((s,i)=>{const x=s.start_minute/2,y=STATUS_Y[s.status],end=s.end_minute/2;const next=day.segments[i+1],line=`H ${end}${next?` V ${STATUS_Y[next.status]}`:''}`;return `${i===0?`M ${x} ${y}`:''} ${line}`}).join(' ');const totals=day.totals;
 return <article className="paper-log"><div className="paper-topline"><b>DRIVER’S DAILY LOG</b><span>ONE CALENDAR DAY · 24 HOURS</span><span><b>Original</b> — file at home terminal<br/><b>Duplicate</b> — driver retains for 8 days</span></div><div className="paper-date"><div className="date-number"><span>{fmtDate(day.date).toUpperCase()}</span><b>{day.date}</b></div><div className="trip-from"><small>FROM</small><b>{from}</b></div><div className="trip-to"><small>TO</small><b>{to}</b></div></div>
  <div className="paper-fields"><div><b>{Math.round(routeMiles).toLocaleString()}</b><small>TOTAL MILES DRIVING TODAY</small></div><div><b>________________</b><small>TOTAL MILEAGE / ODOMETER</small></div><div><b>_______________________________</b><small>NAME OF CARRIER OR CARRIERS</small></div><div><b>_______________________________</b><small>VEHICLE / TRAILER / LICENSE PLATE</small></div><div><b>_______________________________</b><small>MAIN OFFICE ADDRESS</small></div><div><b>_______________________________</b><small>DRIVER NAME / SIGNATURE</small></div></div>
  <div className="graph"><div className="graph-corner">DUTY<br/>STATUS</div><div className="graph-hours">{Array.from({length:25},(_,i)=><span key={i}>{i===0?'M':i===12?'N':i===24?'M':i}</span>)}</div><div className="graph-labels"><span>1. Off Duty</span><span>2. Sleeper Berth</span><span>3. Driving</span><span>4. On Duty<br/>(not driving)</span></div><svg className="graph-svg" viewBox="0 0 720 112" preserveAspectRatio="none" aria-label="24 hour duty status graph">{Array.from({length:25},(_,i)=><line key={'v'+i} x1={i*30} y1="0" x2={i*30} y2="100" className={i%2===0?'major-grid':'minor-grid'}/>)}{[0,1,2,3].map(i=><line key={'h'+i} x1="0" y1={i*25+5} x2="720" y2={i*25+5} className="status-grid"/>)}<path d={path} className="status-trace"/></svg><div className="graph-total">{['offduty','sleeper','driving','onduty'].map(key=><span key={key}>{duration(totals[key])}</span>)}</div></div>
  <div className="remarks"><b>REMARKS / DUTY CHANGE LOCATIONS</b><div className="remarks-lines">{day.events?.map((ev,i)=><span key={i}>{fmtTime(ev.start)} · {ev.label}{ev.cumulative_miles?` · ${ev.cumulative_miles} mi`:''}</span>)}</div><small>Enter shipper, commodity and shipment documents when applicable.</small></div><div className="paper-foot"><span>OFF DUTY <b>{duration(totals.offduty)}</b></span><span>SLEEPER <b>{duration(totals.sleeper)}</b></span><span>DRIVING <b>{duration(totals.driving)}</b></span><span>ON DUTY <b>{duration(totals.onduty)}</b></span></div></article>
}
ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
