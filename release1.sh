#!/bin/bash

# ==========================
# 300개 동시 요청 유지 부하 테스트 (180초 유지)
# ==========================

ENDPOINT="http://192.168.0.2:31113/s0"
LOG_FILE="result_dynamic.log"
CONCURRENT=1000       # 항상 유지할 동시 요청 개수
DURATION=180          # 유지 시간(초)

# 초기화
> "$LOG_FILE"
TMPFILE=$(mktemp)
echo "▶ $CONCURRENT개 요청을 유지하며 $DURATION초 동안 부하를 전송합니다."

# 통계 변수
TOTAL_REQUESTS=0
SUCCESS_COUNT=0
ERROR_COUNT=0
RESPONSE_TIMES=()
SUCCESS_TIMES=()

# 현재 동작 중인 요청 수를 추적
active=0
start_time=$(date +%s)

# 요청 실행 함수
send_request() {
  START=$(date +%s.%N)
  RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" "$ENDPOINT")
  END=$(date +%s.%N)
  DURATION_SEC=$(awk "BEGIN {print $END - $START}")
  
  if [ "$RESPONSE" -eq 200 ]; then
    echo "[✔] 성공 (${DURATION_SEC}s)"
  else
    echo "[✘] 에러: 코드=$RESPONSE (${DURATION_SEC}s)"
  fi
  
  echo "$RESPONSE,$DURATION_SEC" >> "$TMPFILE"
}

# 지정된 시간 동안 지속적으로 요청 유지
while true; do
  current_time=$(date +%s)
  elapsed=$((current_time - start_time))

  # 제한 시간(180초) 초과 시 새로운 요청 추가 중단
  if [ $elapsed -ge $DURATION ]; then
    echo "⏱ 유지 시간($DURATION초) 종료 — 새로운 요청 중단"
    break
  fi

  # 현재 백그라운드 요청 개수 확인
  running=$(jobs -r | wc -l)

  # 부족하면 새 요청을 추가하여 300개 유지
  missing=$((CONCURRENT - running))
  if [ $missing -gt 0 ]; then
    for ((i=0; i<missing; i++)); do
      send_request &
    done
  fi

  # CPU 점유율 과도 방지 (0.5초 단위로 체크)
  sleep 0.5
done

# 180초 이후에는 새로운 요청은 보내지 않지만, 남은 요청이 끝날 때까지 대기
echo "🕓 남은 요청이 종료될 때까지 대기 중..."
wait

# 결과 집계
while IFS=',' read -r code time; do
  ((TOTAL_REQUESTS++))
  if [ "$code" -eq 200 ]; then
    ((SUCCESS_COUNT++))
    SUCCESS_TIMES+=("$time")
  else
    ((ERROR_COUNT++))
  fi
done < "$TMPFILE"

rm -f "$TMPFILE"

# 성공 응답시간 통계
sum=0; max=0; min=999999
for time in "${SUCCESS_TIMES[@]}"; do
  sum=$(awk "BEGIN {print $sum + $time}")
  comp=$(awk "BEGIN {print ($time > $max)}"); if [ "$comp" -eq 1 ]; then max=$time; fi
  comp=$(awk "BEGIN {print ($time < $min)}"); if [ "$comp" -eq 1 ]; then min=$time; fi
done
if [ "$SUCCESS_COUNT" -gt 0 ]; then
  avg=$(awk "BEGIN {print $sum / $SUCCESS_COUNT}")
else
  avg=0; min=0; max=0
fi

# 파드 재시작 합계
RESTART_SUM=$(kubectl get pods -n default -o jsonpath='{range .items[*]}{range .status.containerStatuses[*]}{.restartCount}{"\n"}{end}{end}' 2>/dev/null \
  | awk '{sum+=$1} END {print sum}')

{
  echo ""
  echo "✅ 지속 부하 테스트 완료"
  echo "총 요청 수: $TOTAL_REQUESTS"
  echo "성공 수: $SUCCESS_COUNT"
  echo "에러 수: $ERROR_COUNT"
  echo ""
  echo "📊 성공 요청 응답시간 (초)"
  echo " - 평균: $avg"
  echo " - 최소: $min"
  echo " - 최대: $max"
  echo ""
  echo "🔄 컨테이너 재시작 총합: ${RESTART_SUM:-N/A} 회"
} | tee -a "$LOG_FILE"

echo ""
echo "📁 최종 결과가 $LOG_FILE 에 저장되었습니다."
