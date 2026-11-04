// 디자인 시스템의 아이콘 자리. 장식 아이콘은 aria-hidden, 뜻이 있는 아이콘은 곁의 글자나 접근성 이름이 말해 준다.
const PATHS = {
  bell: 'M12 3a6 6 0 0 0-6 6v3.2l-1.6 2.9A1 1 0 0 0 5.3 16.5h13.4a1 1 0 0 0 .9-1.4L18 12.2V9a6 6 0 0 0-6-6Zm-2 15a2 2 0 0 0 4 0',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4.2a1.1 1.1 0 1 1 0 2.2 1.1 1.1 0 0 1 0-2.2ZM11 11h2v6h-2z',
  close: 'M6 6l12 12M18 6 6 18',
  chevronDown: 'm6 9 6 6 6-6',
  chevronUp: 'm6 15 6-6 6 6',
  chevronLeft: 'm15 6-6 6 6 6',
  chevronRight: 'm9 6 6 6-6 6',
  sortUp: 'M12 6l5 6H7z',
  sortDown: 'M12 18l-5-6h10z',
  warning: 'M12 3 2 20h20L12 3Zm-1 7h2v5h-2zm0 6.5h2v2h-2z',
  sparkle: 'M12 2c.6 4.6 2.4 7.4 8 8-5.6.6-7.4 3.4-8 8-.6-4.6-2.4-7.4-8-8 5.6-.6 7.4-3.4 8-8Z',
  plus: 'M12 5v14M5 12h14',
  minus: 'M5 12h14',
  download: 'M12 4v11m0 0 4-4m-4 4-4-4M5 19h14',
  spinner: 'M12 3a9 9 0 1 0 9 9',
  filter: 'M4 6h16M7 12h10M10 18h4',
  building: 'M4 21V5a1 1 0 0 1 1-1h9a1 1 0 0 1 1 1v16M15 10h4a1 1 0 0 1 1 1v10M3 21h18M8 8h3M8 12h3M8 16h3',
  link: 'M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1',
  document: 'M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1ZM14 3v5h5M9 13h6M9 17h6',
};
const STROKE = new Set(['filter', 'close', 'chevronDown', 'chevronUp', 'chevronLeft', 'chevronRight', 'plus', 'minus', 'download', 'spinner', 'bell', 'building', 'link', 'document']);

export default function Icon({ name, size = 20, className, title }) {
  const stroke = STROKE.has(name);
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill={stroke ? 'none' : 'currentColor'}
      stroke={stroke ? 'currentColor' : 'none'}
      strokeWidth={stroke ? 2 : 0}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden={title ? undefined : true}
      role={title ? 'img' : undefined}
      aria-label={title}
    >
      <path d={PATHS[name]} />
    </svg>
  );
}
