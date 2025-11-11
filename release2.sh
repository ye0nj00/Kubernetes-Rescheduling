#!/bin/bash

ALGO=$1

# ==========================
# main.py 실행 중 300개 요청 지속 유지 부하 테스트
# ==========================

ENDPOINT="http://192.168.0.2:31113/s0"
LOG_FILE="result_mainwatch.log"
CONCURRENT=1000   # 유지할 요청 수
TMPFILE=$(mktemp)
MAIN_SCRIPT="main.py"

# 로그 초기화
> "$LOG_FILE"

echo "▶ 실험 시작"
echo "▶ $MAIN_SCRIPT ($ALGO)을(를) 백그라운드에서 실행합니다..."
python3 "$MAIN_SCRIPT" "$ALGO" &
MAIN_PID=$!

echo "🧩 main.py PID: $MAIN_PID"
echo "🌀 main.py 실행 중에 $CONCURRENT개의 요청을 지속 유지합니다."

# 통계 변수
TOTAL_REQUESTS=0
SUCCESS_COUNT=0
ERROR_COUNT=0
SUCCESS_TIMES=()
RESPONSE_TIMES=()

# 요청 함수
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

# 지속 부하 루프: main.py 실행 중 유지
while kill -0 "$MAIN_PID" 2>/dev/null; do
  running=$(jobs -r | wc -l)
  missing=$((CONCURRENT - running))
  if [ $missing -gt 0 ]; then
    for ((i=0; i<missing; i++)); do
      send_request &
    done
  fi
  sleep 0.5
done

echo "⏹ main.py 종료 감지됨. 새로운 요청 중단."
echo "🕓 남은 요청 완료 대기 중..."
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

# 응답 시간 통계
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
  echo "✅ main.py 기반 지속 부하 테스트 완료"
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
