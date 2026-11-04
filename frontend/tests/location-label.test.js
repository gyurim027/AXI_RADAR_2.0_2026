import test from 'node:test';
import assert from 'node:assert/strict';
import { toLocation } from '../src/api/locationLabel.js';

test('어린이집·유치원은 이름을 숨기고 종류만 보인다', () => {
  const r = toLocation({ address: '성남시 수정구 신흥동 1', landmark: '해님 어린이집', address_source: '어린이집·유치원', landmark_source: '어린이집·유치원' });
  assert.deepEqual(r, { address: '성남시 수정구 신흥동 1', landmark: '어린이집 인근' });
});

test('보호구역 시설은 이름을 숨기고 보호구역 인근으로 부른다', () => {
  assert.equal(toLocation({ address: '주소', landmark: '신흥초등학교', landmark_source: '보호구역 시설' }).landmark, '보호구역 인근');
});

test('버스정류소는 이름을 그대로 보인다', () => {
  assert.equal(toLocation({ address: null, landmark: '신흥역', landmark_source: '버스정류소' }).landmark, '신흥역');
});

test('횡단보도·CCTV·보안등은 이름이 없어도 주소 출처 종류로 부른다', () => {
  assert.equal(toLocation({ address: '도로명 주소', landmark: null, address_source: '횡단보도' }).landmark, '횡단보도 인근');
  assert.equal(toLocation({ address: '도로명 주소', address_source: '안전 CCTV' }).landmark, 'CCTV 인근');
  assert.equal(toLocation({ address: '도로명 주소', address_source: '보안등' }).landmark, '보안등 인근');
});

test('출처를 모르는 이름은 보이지 않는다', () => {
  assert.equal(toLocation({ address: '주소', landmark: '어딘가 이름', landmark_source: '알 수 없음' }).landmark, null);
  assert.equal(toLocation({ address: '주소', landmark: '어딘가 이름' }).landmark, null);
});

test('값이 없으면 null이고 가짜 값을 만들지 않는다', () => {
  assert.deepEqual(toLocation({}), { address: null, landmark: null });
  assert.deepEqual(toLocation(null), { address: null, landmark: null });
  assert.deepEqual(toLocation({ address: '  ', landmark: '' }), { address: null, landmark: null });
});

test('공백을 정리한다', () => {
  assert.equal(toLocation({ address: '  성남시   수정구  ' }).address, '성남시 수정구');
});
