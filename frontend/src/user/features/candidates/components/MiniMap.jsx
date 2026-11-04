import { useEffect, useRef } from 'react';
import L from 'leaflet';
import './CandidateMap.css';
import { addHatchPattern, mapColors } from './mapUtils.js';
import { pointIcon } from './mapPoints.js';
import { COMMON } from '../../../../shared/copy/common.js';
import styles from './MiniMap.module.css';

/** ① 순위 근거 아래 확대 지도 (높이 240px). 이 구역과 근거 지점만 보인다. */
export default function MiniMap({ bounds, points, tier = 'rest' }) {
  const ref = useRef(null);
  useEffect(() => {
    const c = mapColors();
    const map = L.map(ref.current, {
      zoomControl: false,
      attributionControl: false,
      keyboard: false,
      dragging: false,
      scrollWheelZoom: false,
      doubleClickZoom: false,
      boxZoom: false,
      touchZoom: false,
    });
    map.getContainer().classList.add('rmap');
    const renderer = L.svg({ padding: 0.5 }).addTo(map);
    addHatchPattern(renderer, c);
    const fill = tier === 'top' ? c.level3 : tier === 'mid' ? c.level2 : c.level1;
    L.rectangle(bounds, { renderer, color: c.halo, weight: 3.5, fill: false }).addTo(map);
    L.rectangle(bounds, { renderer, color: c.selected, weight: 3, fillColor: fill, fillOpacity: 1 }).addTo(map);
    (points || []).forEach((p) => L.marker([p.lat, p.lon], { icon: pointIcon('site'), interactive: false, keyboard: false }).addTo(map));
    map.fitBounds(bounds, { padding: [24, 24], animate: false });
    return () => map.remove();
  }, [bounds, points, tier]);
  return (
    <figure className={styles.fig}>
      <div ref={ref} className={styles.map} role="img" aria-label={points ? COMMON.rangeText(points.length) : COMMON.rangeUnknown} />
      <figcaption className={styles.cap}>{points ? COMMON.rangeText(points.length) : COMMON.rangeUnknown}</figcaption>
    </figure>
  );
}
