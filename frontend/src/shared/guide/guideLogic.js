// 화면 안내(코치마크)의 순수 계산. 화면과 저장소에 닿지 않아 단독으로 시험한다.
export const SEEN_KEY = 'radar.guide.seen.v1';

/** 이 역할에 보이는 단계만 남긴다. roles가 없는 단계는 모두에게 보인다. */
export function filterSteps(steps, role) {
  return steps.filter((s) => !s.roles || s.roles.includes(role));
}

/** 단계 번호를 0 ~ (개수-1) 안으로 맞춘다. */
export function clampIndex(index, count) {
  if (count <= 0) return 0;
  return Math.min(Math.max(index, 0), count - 1);
}

/** 주소(쿼리·해시 제외)에 맞는 안내 화면을 찾는다. */
export function findScreen(screens, pathname) {
  const path = String(pathname || '').split(/[?#]/)[0];
  return screens.find((s) => s.match.test(path)) || null;
}

function read(storage) {
  try {
    const v = JSON.parse(storage.getItem(SEEN_KEY) || '{}');
    return v && typeof v === 'object' ? v : {};
  } catch {
    return {};
  }
}

/** 이 화면 안내를 이미 봤는지. 저장소를 못 쓰면 본 적 없는 것으로 본다. */
export function hasSeen(storage, key) {
  return read(storage)[key] === true;
}

/** 본 화면으로 기록한다. 저장소를 못 써도 오류 없이 넘어간다. */
export function markSeen(storage, key) {
  try {
    storage.setItem(SEEN_KEY, JSON.stringify({ ...read(storage), [key]: true }));
  } catch {
    // 저장을 막은 환경에서는 매번 안내가 보일 수 있다
  }
}

/** 안내 기록을 모두 지운다 (처음 상태로). */
export function resetSeen(storage) {
  try {
    storage.removeItem(SEEN_KEY);
  } catch {
    // 무시
  }
}

/**
 * 안내 카드 자리. 대상 오른쪽 → 왼쪽 → 아래 → 위 순서로 화면 안에 드는 곳을 고른다.
 * anchor와 viewport는 { left, top, width, height }·{ width, height }, size는 카드 크기다.
 */
export function placeCoach(anchor, size, viewport, gap = 16, margin = 12) {
  const clampX = (x) => Math.min(Math.max(x, margin), Math.max(margin, viewport.width - size.width - margin));
  const clampY = (y) => Math.min(Math.max(y, margin), Math.max(margin, viewport.height - size.height - margin));
  const right = anchor.left + anchor.width + gap;
  const left = anchor.left - gap - size.width;
  const below = anchor.top + anchor.height + gap;
  const above = anchor.top - gap - size.height;
  const centerY = anchor.top + anchor.height / 2 - size.height / 2;
  const centerX = anchor.left + anchor.width / 2 - size.width / 2;
  if (right + size.width <= viewport.width - margin) return { side: 'right', left: right, top: clampY(centerY) };
  if (left >= margin) return { side: 'left', left, top: clampY(centerY) };
  if (below + size.height <= viewport.height - margin) return { side: 'below', left: clampX(centerX), top: below };
  if (above >= margin) return { side: 'above', left: clampX(centerX), top: above };
  return { side: 'over', left: clampX(centerX), top: clampY(centerY) };
}

/**
 * 이 화면이 역할의 핵심 경로에서 몇 번째인지, 다음 화면이 무엇인지 구한다.
 * isOpen(path)가 거짓인 화면(서버에 연결되지 않은 화면)은 경로에서 건너뛴다.
 */
export function flowInfo(flows, screens, role, key, isOpen) {
  const order = (flows[role] || []).map((k) => screens.find((s) => s.key === k)).filter((s) => s && isOpen(s.path));
  const idx = order.findIndex((s) => s.key === key);
  if (idx < 0) return { position: null, next: null, order };
  return { position: { index: idx + 1, total: order.length }, next: order[idx + 1] || null, order };
}

/**
 * 안내의 마지막에 붙는 카드. 다음 화면이 있으면 '다음은 ○○' 이동 카드, 경로의 마지막 화면이면 그 화면의 done(다음 역할이 이어서 할 일)을 보인다.
 * 경로 밖 화면이거나 done이 없으면 null이다.
 */
export function closingStep(info, copy) {
  if (!info.position) return null;
  if (info.next) {
    return { kind: 'next', target: info.next.spotlight, scene: 'goto', label: info.next.menuLabel, title: copy.nextTitle(info.next.menuLabel), bullets: info.next.entry, to: info.next.path };
  }
  const current = info.order[info.position.index - 1];
  if (!current?.done) return null;
  return { kind: 'end', target: null, scene: 'done', title: current.done.title, bullets: current.done.bullets };
}
