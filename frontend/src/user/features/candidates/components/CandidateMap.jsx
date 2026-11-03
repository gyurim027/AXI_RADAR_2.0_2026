import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import L from 'leaflet';
import './CandidateMap.css';
import Icon from '../../../components/Icon.jsx';
import { InfoHelp } from '../../../components/FormControls.jsx';
import { COMMON, MAP_COORD_CREDIT, MAP_CREDIT } from '../../../../shared/copy/common.js';
import { LIST } from '../copy.js';
import { singleFingerDragAllowed, wheelZoomAllowed } from '../stackNav.js';
import { addHatchPattern, mapColors, prefersReducedMotion, tierFill } from './mapUtils.js';
import { CLUSTER_LIMIT, basisSummary, clusterIcon, clusterLabel, groupComplaintPoints, pointIcon, pointKind, pointLabel } from './mapPoints.js';
import styles from './CandidateMap.module.css';
import { placeLabel } from '../../../../shared/utils/format.js';

// 성남시 둘레. 어두운 막이 지도를 움직여도 빈틈없이 덮고, 지도가 이 밖으로 나가지 않는다.
const DIM_BOUNDS = [
  [37.25, 126.95],
  [37.65, 127.35],
];
const PANEL_MARGIN = 16; // 요약 카드가 지도 위에서 떨어진 거리 (--component-map-card-margin)
const SELECT_ZOOM = 17; // 구역을 고르면 그 칸이 지도에 크게 보이도록 이 단계까지 확대한다 (US-01 1-5)

/**
 * 후보 지도 (US-01 1-5, 디자인 시스템 10장)
 * - 후보 구역은 점검 필요도 파랑 4단계, 평가하지 못한 구역은 회색 빗금
 * - 구역을 누르면 onSelect, 표에서 고른 구역으로 지도가 옮겨 간다
 * - 키보드: 지도에 포커스가 있으면 화살표로 구역을 옮기고 Enter로 고르고 +, -로 확대·축소
 * 지도 바탕 타일은 쓰지 않는다(지도 서비스 미정, 수치지형도 원본은 국외 반출 금지).
 */
export default function CandidateMap({ items, unrated, boundaries, ownGu, selectedId, onSelect, fitKey, cooperative = false, children }) {
  const coopRef = useRef(cooperative);
  const [coopHint, setCoopHint] = useState(null); // 'wheel' | 'touch'
  const elRef = useRef(null);
  const mapRef = useRef(null);
  const viewBeforeRef = useRef(null); // 구역을 고르기 전 지도 보기
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
    // 쌓인 배치(협조 모드): 지도 위 휠은 페이지를 스크롤하고, Ctrl(⌘)+휠일 때만 확대한다. 터치는 두 손가락만 지도를 움직인다.
    const box = map.getContainer();
    let hintTimer = 0;
    const showHint = (kind) => {
      setCoopHint(kind);
      clearTimeout(hintTimer);
      hintTimer = setTimeout(() => setCoopHint(null), 1800);
    };
    const onWheel = (e) => {
      if (wheelZoomAllowed({ cooperative: coopRef.current, ctrlKey: e.ctrlKey, metaKey: e.metaKey })) return;
      e.stopPropagation(); // Leaflet의 휠 확대로 가지 않게 막는다. 페이지는 그대로 스크롤된다.
      showHint('wheel');
    };
    const onTouch = (e) => {
      if (coopRef.current && e.touches.length === 1 && window.matchMedia('(pointer: coarse)').matches) showHint('touch');
    };
    box.addEventListener('wheel', onWheel, { capture: true, passive: true });
    box.addEventListener('touchstart', onTouch, { passive: true });
    map.on('zoomend', () => setZoom(map.getZoom()));
    mapRef.current = map;
    // 분할 막대로 폭이 바뀌는 동안 호출이 몰리지 않게 프레임마다 한 번만 다시 잰다.
    let frame = 0;
    const ro = new ResizeObserver(() => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => map.invalidateSize());
    });
    ro.observe(elRef.current);
    return () => {
      cancelAnimationFrame(frame);
      clearTimeout(hintTimer);
      box.removeEventListener('wheel', onWheel, { capture: true });
      box.removeEventListener('touchstart', onTouch);
      ro.disconnect();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // 협조 모드가 바뀌면(폭이 1100px을 넘나들면) 한 손가락 끌기를 켜고 끈다
  useEffect(() => {
    coopRef.current = cooperative;
    const map = mapRef.current;
    if (!map) return;
    const coarse = window.matchMedia('(pointer: coarse)').matches;
    if (singleFingerDragAllowed({ cooperative, coarse })) map.dragging.enable();
    else map.dragging.disable();
  }, [cooperative]);

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
        rect.bindTooltip(r.points ? COMMON.rangeText(r.points.length) : COMMON.rangeUnknown, { permanent: true, direction: 'bottom', className: 'rmap-range', offset: [0, 4] }).openTooltip();
      }
    });
    // 칸을 고르기 전에는 점을 그리지 않는다. 고른 칸의 근거 지점(■)과 민원 점(● ○)만 그린다 (US-01 1-5, ISS-036)
    if (sel) {
      const addMarker = (latlng, icon, label, onClick) => {
        const m = L.marker(latlng, { icon, keyboard: true, title: label, alt: label });
        // 지도 위쪽 끝에서는 말풍선이 잘리지 않게 아래로 연다
        const nearTop = map.latLngToContainerPoint(latlng).y < 72;
        m.bindTooltip(label, { direction: nearTop ? 'bottom' : 'top', offset: [0, nearTop ? 6 : -6], className: 'rmap-issue' });
        m.on('add', () => {
          const el = m.getElement();
          if (!el) return;
          el.setAttribute('aria-label', label);
          el.addEventListener('focus', () => m.openTooltip());
          el.addEventListener('blur', () => m.closeTooltip());
          if (onClick) el.addEventListener('keydown', (e) => e.key === 'Enter' && onClick());
        });
        if (onClick) m.on('click', onClick);
        m.addTo(points);
      };
      const site = (p) => addMarker([p.lat, p.lon], pointIcon('site'), p.issue);
      const one = (p) => addMarker([p.lat, p.lon], pointIcon(pointKind(p), p.count), pointLabel(p));
      (sel.points || []).forEach(site);
      const complaints = sel.complaintPoints || [];
      if (complaints.length > CLUSTER_LIMIT) {
        // 점이 많은 칸: 가까운 점을 숫자 원으로 묶는다. 누르거나 확대하면 나뉜다 (ISS-038)
        groupComplaintPoints(map, complaints, zoom).forEach((g) => {
          if (g.single) return one(g.single);
          const zoomTo = () => map.fitBounds(L.latLngBounds(g.members.map((p) => [p.lat, p.lon])), { padding: [48, 48], maxZoom: 18, animate: !prefersReducedMotion() });
          addMarker([g.lat, g.lon], clusterIcon(g.count), clusterLabel(g), zoomTo);
        });
      } else {
        complaints.forEach(one);
      }
    }
  }, [all, byId, selectedId, zoom]);

  // 처음과 범위가 바뀔 때 전체가 보이게 맞춘다
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !all.length) return;
    const bounds = L.latLngBounds(all.flatMap((r) => r.bounds));
    map.fitBounds(bounds, { padding: [24, 24], animate: false, maxZoom: 14.5 });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  // 표에서 행을 고르면 지도가 그 구역으로 옮겨 간다. 고르기 전 보기는 기억해 두었다가, 선택을 풀면 그 보기로 돌아온다.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const r = byId.get(selectedId);
    if (!r) {
      const before = viewBeforeRef.current;
      if (before) {
        viewBeforeRef.current = null;
        map.flyTo(before.center, before.zoom, { animate: !prefersReducedMotion(), duration: 0.5 });
      }
      return;
    }
    if (!viewBeforeRef.current) viewBeforeRef.current = { center: map.getCenter(), zoom: map.getZoom() };
    // 요약 패널이 지도 위쪽을 덮으므로, 고른 구역이 패널 아래 남은 면의 가운데에 오도록 중심을 패널 높이의 절반만큼 위로 옮긴다
    const z = Math.max(map.getZoom(), SELECT_ZOOM);
    const center = L.latLng((r.bounds[0][0] + r.bounds[1][0]) / 2, (r.bounds[0][1] + r.bounds[1][1]) / 2);
    const panel = elRef.current?.parentElement?.querySelector('[data-summary-panel]');
    const covered = panel ? panel.offsetHeight + PANEL_MARGIN : map.getSize().y * 0.24;
    const target = map.unproject(map.project(center, z).subtract([0, covered / 2]), z);
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
  const selCell = byId.get(selectedId) || null;
  const clustered = !!selCell && (selCell.complaintPoints?.length || 0) > CLUSTER_LIMIT;
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
        {focused ? placeLabel(focused) : ''}
      </p>

      {children}

      {coopHint ? (
        <p className={styles.coopHint} role="status">
          {coopHint === 'wheel' ? LIST.mapCoopWheel : LIST.mapCoopTouch}
        </p>
      ) : null}

      <div className={styles.zoom}>
        <button type="button" aria-label="지도 확대" onClick={() => mapRef.current?.zoomIn()}>
          <Icon name="plus" size={20} />
        </button>
        <button type="button" aria-label="지도 축소" onClick={() => mapRef.current?.zoomOut()}>
          <Icon name="minus" size={20} />
        </button>
      </div>

      <div className={styles.legendWrap}>
        {clustered ? <p className={styles.clusterNote}>{LIST.clusterNote}</p> : null}
        {/* 격자를 고르면 점검 필요도 범례는 숨긴다. 근거 팝업·이 칸의 근거와 겹치기 때문이다 */}
        {!selCell && legendOpen ? (
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
        ) : null}
        {selCell?.points ? (
          <div className={styles.legendBasis}>
            <p>{LIST.legendBasis(basisSummary(selCell))}</p>
            <p aria-label={LIST.legendShapesLabel}>
              {LIST.legendShapes}
              <InfoHelp label={LIST.evidenceHelpLabel}>{LIST.evidenceHelp}</InfoHelp>
            </p>
            {clustered ? <p>{LIST.legendCluster}</p> : null}
          </div>
        ) : null}
        {!selCell && !legendOpen ? (
          <button type="button" className={styles.legendChip} aria-expanded="false" aria-label={LIST.legendToggle(false)} onClick={() => setLegendOpen(true)}>
            {LIST.legendChip}
          </button>
        ) : null}
      </div>
      <p className={styles.credit}>{selCell ? MAP_COORD_CREDIT : MAP_CREDIT}</p>
    </div>
  );
}
