import { useEffect, useMemo, useRef } from 'react';
import L from 'leaflet';

// Actual WGS84 grid centroids only. Never infer a grid polygon from a point.
export function validCenter(row) {
  const lat = row.centerLat;
  const lon = row.centerLon;
  return typeof lat === 'number' && typeof lon === 'number' && Number.isFinite(lat) && Number.isFinite(lon)
    && lat >= -90 && lat <= 90 && lon >= -180 && lon <= 180;
}

export default function StoredPriorityCenterMap({ rows, selectedGid, onSelect }) {
  const ref = useRef(null);
  const mapRef = useRef(null);
  const points = useMemo(() => rows.filter(validCenter), [rows]);
  useEffect(() => {
    if (!ref.current) return undefined;
    const map = L.map(ref.current, { attributionControl: false, zoomControl: true, preferCanvas: true });
    mapRef.current = map;
    map.setView([37.41, 127.13], 11);
    const layer = L.layerGroup().addTo(map);
    if (points.length) {
      const bounds = [];
      points.forEach(row => {
        const pos = [row.centerLat, row.centerLon];
        bounds.push(pos);
        L.circleMarker(pos, {
          radius: row.gid === selectedGid ? 6 : 3,
          weight: row.gid === selectedGid ? 2 : 1,
          color: row.gid === selectedGid ? '#174a9a' : '#516278',
          fillOpacity: 0.6,
        }).bindTooltip(`격자 ${row.gid}: 저장점수 ${row.score == null ? '미산출' : row.score}`)
          .on('click', () => onSelect(row.gid)).addTo(layer);
      });
      map.fitBounds(bounds, { padding: [20, 20], maxZoom: 14, animate: false });
    }
    return () => { map.remove(); mapRef.current = null; };
  }, [points, onSelect, selectedGid]);
  return <section aria-label="실제 격자 중심점 지도">
    <p>실제 05의 WGS84 중심 좌표만 표시합니다. 점은 격자 경계·근거 지점이 아니며, 점수 색상 구분·승인 상태를 나타내지 않습니다.</p>
    {points.length === 0 && <p role="status">검증 가능한 좌표가 없어 지도 지점을 표시하지 않습니다.</p>}
    {points.length > 0 && points.length !== rows.length && <p role="status">좌표가 없는 {rows.length - points.length}개 격자는 표시하지 않았습니다.</p>}
    <div ref={ref} style={{ height: '340px', width: '100%' }} aria-label="저장 격자 중심점 Leaflet 지도" />
  </section>;
}
