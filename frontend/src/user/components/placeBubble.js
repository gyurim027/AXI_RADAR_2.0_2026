export const MARGIN = 16; // 말풍선과 화면 가장자리 사이 여백

/** 말풍선이 화면 안에 들도록 자리를 정한다. 아래가 모자라면 위로 뒤집고, 옆으로 넘치면 민다. */
export function placeBubble(anchor, size, viewport, gap = 4) {
  const left = Math.min(Math.max(anchor.left, MARGIN), Math.max(MARGIN, viewport.width - size.width - MARGIN));
  const below = anchor.bottom + gap;
  const fitsBelow = below + size.height <= viewport.height - MARGIN;
  const above = anchor.top - gap - size.height;
  const flip = !fitsBelow && above >= MARGIN;
  return { top: flip ? above : below, left, flipped: flip };
}
