export const TAGLINE =
  '아이의 상황을 적으면 검증된 의료 출처를 먼저 찾고, AI 패널이 함께 검토한 답을 하나로 정리해요.';

export const TRUST_SOURCES = ['질병관리청', '대한소아청소년과학회', '식약처', 'WHO', 'AAP'];

export const HERO_STATS = [
  { value: 'Stage 0', label: '신뢰 출처 먼저 확인' },
  { value: '3인 패널', label: '답변 교차검토' },
  { value: '응급 우선', label: '신생아 발열 안전망' },
];

export const CATEGORIES = [
  {
    id: 'fever',
    label: '열·체온',
    examples: ['38도 열이 나는데 해열제를 먹여도 될까요?', '열이 며칠째 안 떨어져요. 언제 병원에 가야 하나요?'],
  },
  {
    id: 'sleep',
    label: '수면',
    examples: ['밤에 자주 깨서 우는 아이, 어떻게 도와줄까요?', '수면 교육은 언제 시작하면 좋을까요?'],
  },
  {
    id: 'feeding',
    label: '먹이기',
    examples: ['6개월 아기 이유식, 어떻게 시작하면 좋을까요?', '분유를 잘 안 먹는데 괜찮을까요?'],
  },
  {
    id: 'development',
    label: '발달',
    examples: ['또래보다 늦게 걷는 것 같아요. 정상인가요?', '말이 느린데 언제 검사를 받아야 하나요?'],
  },
  {
    id: 'other',
    label: '기타',
    examples: ['아이가 자꾸 토하는데 언제 병원에 가야 하나요?', '예방접종 후 열이 나면 어떻게 해야 하나요?'],
  },
];
