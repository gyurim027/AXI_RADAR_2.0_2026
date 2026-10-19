import L from 'leaflet';

/** CSS 토큰 값을 읽는다. 지도 색은 코드에 쓰지 않고 토큰에서 가져온다. */
export function token(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

export function mapColors() {
  return {
    level3: token('--component-map-level-3'),
    level2: token('--component-map-level-2'),
    level1: token('--component-map-level-1'),
    outline: token('--component-map-outline'),
    halo: token('--component-map-halo'),
    selected: token('--component-map-selected'),
    unrated: token('--component-map-unrated-line'),
    base: token('--component-map-bg'),
    border: token('--component-map-border'),
    focus: token('--semantic-color-focus-ring'),
    scrim: token('--semantic-color-text'),
  };
}

export const HATCH_ID = 'radar-unrated-hatch';

/** 평가하지 못한 구역용 45도 빗금 (선 2px) */
export function addHatchPattern(renderer, colors) {
  const svg = renderer._container;
  if (!svg || svg.querySelector(`#${HATCH_ID}`)) return;
  const ns = 'http://www.w3.org/2000/svg';
  const defs = document.createElementNS(ns, 'defs');
  const pattern = document.createElementNS(ns, 'pattern');
  pattern.setAttribute('id', HATCH_ID);
  pattern.setAttribute('patternUnits', 'userSpaceOnUse');
  pattern.setAttribute('width', '7');
  pattern.setAttribute('height', '7');
  pattern.setAttribute('patternTransform', 'rotate(45)');
  const bg = document.createElementNS(ns, 'rect');
  bg.setAttribute('width', '7');
  bg.setAttribute('height', '7');
  bg.setAttribute('fill', colors.base);
  const line = document.createElementNS(ns, 'line');
  line.setAttribute('x1', '0');
  line.setAttribute('y1', '0');
  line.setAttribute('x2', '0');
  line.setAttribute('y2', '7');
  line.setAttribute('stroke', colors.unrated);
  line.setAttribute('stroke-width', '2');
  pattern.append(bg, line);
  defs.append(pattern);
  svg.prepend(defs);
}

/** 근거 지점 점(지름 8px, 흰 테두리 1.5px). 종류는 색이 아니라 모양으로 나눈다. */
export function pointIcon(shape) {
  return L.divIcon({
    className: 'rmap-point-wrap',
    html: `<span class="rmap-point rmap-point--${shape}"></span>`,
    iconSize: [12, 12],
    iconAnchor: [6, 6],
  });
}

export function tierFill(tier, c) {
  if (tier === 'top') return c.level3;
  if (tier === 'mid') return c.level2;
  if (tier === 'rest') return c.level1;
  return `url(#${HATCH_ID})`;
}

export const prefersReducedMotion = () =>
  typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
