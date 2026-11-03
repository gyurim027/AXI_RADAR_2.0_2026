/** 쌓인 배치(1100px 미만)의 지도 제스처와 표·지도 전환 막대 판단. 화면 없이 시험할 수 있게 순수 함수로 둔다. */

/** 지도 위 휠: 협조 모드에서는 Ctrl(맥은 ⌘)을 누른 때만 확대하고, 아니면 페이지가 스크롤된다. */
export function wheelZoomAllowed({ cooperative, ctrlKey, metaKey }) {
  return !cooperative || !!ctrlKey || !!metaKey;
}

/** 터치 기기에서 협조 모드이면 한 손가락 끌기를 끈다(두 손가락 확대·이동만 허용). */
export function singleFingerDragAllowed({ cooperative, coarse }) {
  return !(cooperative && coarse);
}

/**
 * 지금 보이는 구역. 위에서부터 보이는 높이가 더 큰 쪽을 고른다.
 * sections: [{ key, top, bottom }] 화면 위쪽(막대 아래)을 기준으로 한 좌표, viewTop·viewBottom: 보이는 영역
 */
export function activeSection(sections, viewTop, viewBottom) {
  let best = sections[0]?.key ?? null;
  let bestVisible = -1;
  for (const s of sections) {
    const visible = Math.max(0, Math.min(s.bottom, viewBottom) - Math.max(s.top, viewTop));
    if (visible > bestVisible) {
      bestVisible = visible;
      best = s.key;
    }
  }
  return best;
}
