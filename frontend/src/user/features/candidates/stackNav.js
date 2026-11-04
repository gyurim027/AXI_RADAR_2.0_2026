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
 * 지금 보이는 구역. 맨 위에 있으면 첫 구역, 맨 아래에 닿으면 마지막 구역, 그 사이는 보이는 높이가 더 큰 쪽이다.
 * sections: [{ key, top, bottom }] 스크롤 영역 위쪽을 기준으로 한 좌표, viewTop·viewBottom: 보이는 영역(막대 아래부터)
 */
export function activeSection(sections, viewTop, viewBottom, { atTop = false, atBottom = false } = {}) {
  if (!sections.length) return null;
  if (atBottom && sections.length > 1) return sections[sections.length - 1].key;
  if (atTop) return sections[0].key;
  let best = sections[0].key;
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

/** 탭을 눌렀을 때 스크롤할 위치. 맨 위 구역은 0, 맨 아래 구역은 끝, 그 밖은 구역 시작이 막대 바로 아래에 오게 한다. */
export function scrollTarget({ edge, sectionTop, barHeight, scrollHeight, clientHeight }) {
  if (edge === 'top') return 0;
  if (edge === 'bottom') return Math.max(0, scrollHeight - clientHeight);
  return Math.max(0, sectionTop - barHeight);
}
