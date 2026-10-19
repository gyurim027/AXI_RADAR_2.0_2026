import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import './CandidateMap.css';
import Icon from '../../../components/Icon.jsx';
import { COMMON, MAP_CREDIT } from '../../../../shared/copy/common.js';
import { LIST } from '../copy.js';
import { addHatchPattern, mapColors, pointIcon, prefersReducedMotion, tierFill } from './mapUtils.js';
import styles from './CandidateMap.module.css';

// 성남시 둘레. 어두운 막이 지도를 움직여도 빈틈없이 덮고, 지도가 이 밖으로 나가지 않는다.
const DIM_BOUNDS = [
  [37.25, 126.95],
  [37.65, 127.35],
];
const POINT_ZOOM = 15; // 이 확대 단계부터 모든 근거 지점을 보인다. 그보다 멀 때는 고른 구역의 점만 보인다.

/**
 * 후보 지도 (US-01 1-5, 디자인 시스템 10장)
 * - 후보 구역은 점검 필요도 파랑 4단계, 평가하지 못한 구역은 회색 빗금
 * - 구역을 누르면 onSelect, 표에서 고른 구역으로 지도가 옮겨 간다
 * - 키보드: 지도에 포커스가 있으면 화살표로 구역을 옮기고 Enter로 고르고 +, -로 확대·축소
 * 지도 바탕 타일은 쓰지 않는다(지도 서비스 미정, 수치지형도 원본은 국외 반출 금지).
 */
export default function CandidateMap({ items, unrated, boundaries, ownGu, selectedId, onSelect, fitKey, children }) {
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const layersRef = useRef({ cells: null, points: null, bounds: null, focus: null });
  const rendererRef = useRef(null);
  const topRendererRef = useRef(null);
  const dimRendererRef = useRef(null);
  const [legendOpen, setLegendOpen] = useState(true);
  const colorsRef = useRef(null);
  const [zoom, setZoom] = useState(12);
  const [focusId, setFocusId] = useState(null);
  const onSelectRef = useRef(onSelect);
  useEffect(() => {
    onSelectRef.current = onSelect;
  });

  const all = useMemo(() => [...items, ...unrated], [items, unrated]);
  const allRef = useRef(all);
  useEffect(() => {
    allRef.current = all;
  }, [all]);
  const byId = useMemo(() => new Map(all.map((r) => [r.gid, r])), [all]);

  // 지도 만들기 (한 번)
  useEffect(() => {
    const colors = mapColors();
    colorsRef.current = colors;
    const map = L.map(elRef.current, {
      zoomControl: false,
      attributionControl: false,
      keyboard: false, // 화살표 키는 구역 이동에 쓴다
      zoomSnap: 0.5,
      minZoom: 10,
      maxZoom: 18,
      preferCanvas: false,
    });
    map.getContainer().classList.add('rmap');
    const renderer = L.svg({ padding: 0.5 });
    renderer.addTo(map);
    rendererRef.current = renderer;
    addHatchPattern(renderer, colors);
    // 구역을 누르면 배경을 어둡게 하고 고른 구역만 막 위에 선명하게 둔다 (와이어프레임 5-2)
    map.createPane('dim').style.zIndex = '450';
    map.createPane('selCell').style.zIndex = '460';
    const dimRenderer = L.svg({ pane: 'dim', padding: 0.5 }).addTo(map);
    const topRenderer = L.svg({ pane: 'selCell', padding: 0.5 }).addTo(map);
    addHatchPattern(topRenderer, colors);
    dimRendererRef.current = dimRenderer;
    topRendererRef.current = topRenderer;
    map.setMaxBounds(L.latLngBounds(DIM_BOUNDS));
    layersRef.current = {
      dim: L.layerGroup().addTo(map),
      bounds: L.layerGroup().addTo(map),
      cells: L.layerGroup().addTo(map),
      points: L.layerGroup().addTo(map),
      focus: L.layerGroup().addTo(map),
    };
    map.setView([37.41, 127.13], 12);
    map.on('zoomend', () => setZoom(map.getZoom()));
    mapRef.current = map;
    const ro = new ResizeObserver(() => map.invalidateSize());
    ro.observe(elRef.current);
    return () => {
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 구 경계. 도로관리팀은 자기 구 밖을 흐리게 보인다 (US-01 1-5)
  useEffect(() => {
    const map = mapRef.current;
    const c = colorsRef.current;
    if (!map || !boundaries) return;
    const group = layersRef.current.bounds;
    group.clearLayers();
    Object.entries(boundaries).forEach(([gu, pts]) => {
      const outside = ownGu && gu !== ownGu;
      L.polygon(pts, {
        renderer: rendererRef.current,
        interactive: false,
        color: c.border,
        weight: 1,
        dashArray: '4 4',
        fillColor: outside ? c.border : c.base,
        fillOpacity: outside ? 0.35 : 0,
      }).addTo(group);
    });
  }, [boundaries, ownGu]);

  // 구역과 근거 지점
  useEffect(() => {
    const map = mapRef.current;
    const c = colorsRef.current;
    if (!map) return;
    const { cells, points, dim } = layersRef.current;
    cells.clearLayers();
    points.clearLayers();
    dim.clearLayers();
    const sel = byId.get(selectedId) || null;
    // 구역을 고르면 배경 전체를 어둡게 한다. 다른 구역도 막 아래에서 눌러 고를 수 있다.
    if (sel) {
      L.rectangle(DIM_BOUNDS, { renderer: dimRendererRef.current, pane: 'dim', interactive: false, stroke: false, fillColor: c.scrim, fillOpacity: 0.5 }).addTo(dim);
    }
    all.forEach((r) => {
      const isSel = sel && r.gid === sel.gid;
      const renderer = isSel ? topRendererRef.current : rendererRef.current;
      const pane = isSel ? 'selCell' : undefined;
      // 구역마다 1.5px 파랑 테두리 바깥에 1px 흰 테두리를 더한다
      L.rectangle(r.bounds, { renderer, pane, interactive: false, color: c.halo, weight: isSel ? 5 : 3.5, fill: false }).addTo(cells);
      const rect = L.rectangle(r.bounds, {
        renderer,
        pane,
        color: isSel ? c.selected : c.outline,
        weight: isSel ? 3 : 1.5,
        fillColor: tierFill(r.tier, c),
        fillOpacity: 1,
        bubblingMouseEvents: false,
      });
      rect.on('click', () => onSelectRef.current?.(r.gid));
      rect.addTo(cells);
      if (isSel) {
        // 후보 범위 표시 (CM-00 4번): 고른 구역을 네모 영역으로 칠하고 근거 지점 수를 적는다
        rect.bindTooltip(COMMON.rangeText(r.points.length), { permanent: true, direction: 'bottom', className: 'rmap-range', offset: [0, 4] }).openTooltip();
      }
      // 구역을 고르면 그 구역의 근거 지점만 보인다. 고르지 않았을 때는 확대하면 모두 보인다.
      if (isSel || (!sel && zoom >= POINT_ZOOM)) {
        r.points.forEach((p) => {
          // 지점에 마우스를 올리거나 포커스가 오면 보행 문제 유형이 뜬다 (와이어프레임 5-2)
          const m = L.marker([p.lat, p.lon], { icon: pointIcon(p.shape), keyboard: true, title: p.issue, alt: p.issue });
          m.bindTooltip(p.issue, { direction: 'top', offset: [0, -6], className: 'rmap-issue' });
          m.on('add', () => {
            const el = m.getElement();
            if (!el) return;
            el.setAttribute('aria-label', p.issue);
            el.addEventListener('focus', () => m.openTooltip());
            el.addEventListener('blur', () => m.closeTooltip());
          });
          m.addTo(points);
        });
      }
    });
  }, [all, byId, selectedId, zoom]);

  // 처음과 범위가 바뀔 때 전체가 보이게 맞춘다
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !all.length) return;
    const bounds = L.latLngBounds(all.flatMap((r) => r.bounds));
    map.fitBounds(bounds, { padding: [24, 24], animate: false, maxZoom: 14.5 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  // 표에서 행을 고르면 지도가 그 구역으로 옮겨 간다
  useEffect(() => {
    const map = mapRef.current;
    const r = byId.get(selectedId);
    if (!map || !r) return;
    // 요약 패널이 지도 위쪽을 덮으므로, 고른 구역이 패널 아래에 오도록 중심을 조금 위로 옮긴다
    const z = Math.max(map.getZoom(), 15);
    const center = L.latLng((r.bounds[0][0] + r.bounds[1][0]) / 2, (r.bounds[0][1] + r.bounds[1][1]) / 2);
    const target = map.unproject(map.project(center, z).subtract([0, map.getSize().y * 0.2]), z);
    map.flyTo(target, z, { animate: !prefersReducedMotion(), duration: 0.5 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId]);

  // 키보드로 옮기는 중인 구역: 3px 포커스 테두리
  useEffect(() => {
    const c = colorsRef.current;
    const group = layersRef.current.focus;
    if (!group) return;
    group.clearLayers();
    const r = byId.get(focusId);
    if (r) L.rectangle(r.bounds, { renderer: rendererRef.current, interactive: false, color: c.focus, weight: 3, fill: false, dashArray: '2 3' }).addTo(group);
  }, [focusId, byId]);

  const moveFocus = useCallback(
    (dir) => {
      const list = allRef.current;
      if (!list.length) return;
      const center = (r) => [(r.bounds[0][0] + r.bounds[1][0]) / 2, (r.bounds[0][1] + r.bounds[1][1]) / 2];
      const cur = list.find((r) => r.gid === focusId) || list.find((r) => r.gid === selectedId) || list[0];
      if (!focusId && !selectedId) {
        setFocusId(cur.gid);
        return;
      }
      const [cy, cx] = center(cur);
      const dirs = { ArrowUp: [1, 0], ArrowDown: [-1, 0], ArrowLeft: [0, -1], ArrowRight: [0, 1] };
      const [dy, dx] = dirs[dir];
      let best = null;
      let bestScore = Infinity;
      list.forEach((r) => {
        if (r.gid === cur.gid) return;
        const [y, x] = center(r);
        const vy = (y - cy) * 111320;
        const vx = (x - cx) * 88400;
        const along = vy * dy + vx * dx;
        if (along <= 1) return;
        const across = Math.abs(vy * dx) + Math.abs(vx * dy);
        const score = along + across * 2;
        if (score < bestScore) {
          bestScore = score;
          best = r;
        }
      });
      if (best) {
        setFocusId(best.gid);
        mapRef.current?.panTo(center(best), { animate: !prefersReducedMotion() });
      }
    },
    [focusId, selectedId],
  );

  const onKeyDown = (e) => {
    if (e.key.startsWith('Arrow')) {
      e.preventDefault();
      moveFocus(e.key);
    } else if (e.key === 'Enter' && focusId) {
      e.preventDefault();
      onSelect?.(focusId);
    } else if (e.key === '+' || e.key === '=') {
      mapRef.current?.zoomIn();
    } else if (e.key === '-' || e.key === '_') {
      mapRef.current?.zoomOut();
    }
  };

  const focused = byId.get(focusId);
  return (
    <div className={styles.wrap}>
      <div
        ref={elRef}
        className={styles.map}
        tabIndex={0}
        role="application"
        aria-label={LIST.mapLabel}
        aria-describedby="map-help"
        onKeyDown={onKeyDown}
        onBlur={() => setFocusId(null)}
      />
      <p id="map-help" className="sr-only">
        화살표 키로 구역을 옮기고 Enter 키로 고릅니다. 더하기, 빼기 키로 확대하고 축소합니다. 모든 구역은 왼쪽 표에도 있습니다.
      </p>
      <p className="sr-only" aria-live="polite">
        {focused ? `${focused.address} · ${focused.landmark}` : ''}
      </p>

      {children}

      <div className={styles.zoom}>
        <button type="button" aria-label="지도 확대" onClick={() => mapRef.current?.zoomIn()}>
          <Icon name="plus" size={20} />
        </button>
        <button type="button" aria-label="지도 축소" onClick={() => mapRef.current?.zoomOut()}>
          <Icon name="minus" size={20} />
        </button>
      </div>

      <div className={styles.legendWrap}>
        {legendOpen ? (
          <>
            <button type="button" className={styles.legendToggle} aria-expanded="true" aria-label={LIST.legendToggle(true)} onClick={() => setLegendOpen(false)}>
              <Icon name="chevronDown" size={18} />
            </button>
            <ul className={styles.legend}>
              {LIST.legend.map((label, i) => (
                <li key={label}>
                  <span className={`${styles.swatch} ${styles[`sw${i}`]}`} aria-hidden="true" />
                  {label}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <button type="button" className={styles.legendChip} aria-expanded="false" aria-label={LIST.legendToggle(false)} onClick={() => setLegendOpen(true)}>
            {LIST.legendChip}
            <Icon name="chevronUp" size={16} />
          </button>
        )}
      </div>
      <p className={styles.credit}>{MAP_CREDIT}</p>
    </div>
  );
}
