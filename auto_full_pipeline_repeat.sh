#!/bin/bash
# ===================================================
# 🧩 µBench 전체 자동화 실험 스크립트 (알고리즘 × 반복)
# ===================================================

# 알고리즘 목록
ALGORITHMS=("spread" "binpack" "random" "kubescheduling" "communication")

# 반복 횟수
REPEAT=5

# 상위 결과 디렉터리
BASE_RESULT_DIR="./result"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SESSION_DIR="${BASE_RESULT_DIR}/session_${TIMESTAMP}"
mkdir -p "$SESSION_DIR"

echo "📁 세션 디렉터리 생성: $SESSION_DIR"
echo "🧩 알고리즘 목록: ${ALGORITHMS[*]}"
echo "🔁 각 알고리즘당 ${REPEAT}회 반복 실행"

# ===================================================
# 🔁 알고리즘 반복 루프
# ===================================================
for algo in "${ALGORITHMS[@]}"; do
  echo ""
  echo "==================================================="
  echo "🚀 알고리즘: $algo 시작"
  echo "==================================================="

  # 알고리즘별 결과 디렉터리
  ALGO_DIR="${SESSION_DIR}/${algo}"
  mkdir -p "$ALGO_DIR"

  # --------------------------------------------------
  # 🔁 5회 반복 루프
  # --------------------------------------------------
  for ((run=1; run<=REPEAT; run++)); do
    echo ""
    echo "---------------------------------------------------"
    echo "▶ 실험 ${run}/${REPEAT} (${algo})"
    echo "---------------------------------------------------"

    RUN_DIR="${ALGO_DIR}/run_${run}"
    mkdir -p "$RUN_DIR"

    # 1. cordon
    echo "▶ Step 1: worker2, worker3 cordon"
    kubectl cordon worker2
    kubectl cordon worker3
    sleep 5

    # 2. mubench 배포 (알고리즘 지정 추가)
    echo "▶ Step 2: mubench 컨테이너 진입 및 ${algo} 알고리즘 배포 실행"
    docker exec -i mubench bash <<EOF
python3 Deployers/K8sDeployer/RunK8sDeployer.py -c Configs/K8sParameters.json
exit
EOF

    # 3. imagePullPolicy 수정
    echo "▶ Step 3: imagePullPolicy → IfNotPresent"
    for d in $(kubectl get deploy -o name); do
      n=$(kubectl get $d -o jsonpath='{.spec.template.spec.containers[*].name}' | wc -w)
      for i in $(seq 0 $((n-1))); do
        kubectl patch $d --type='json' \
          -p="[{\"op\":\"replace\",\"path\":\"/spec/template/spec/containers/$i/imagePullPolicy\",\"value\":\"IfNotPresent\"}]" \
          && echo "[$d] container $i patched" \
          || echo "[$d] container $i patch failed"
      done
    done

    kubectl delete po --all --force

    # 4. 모든 파드 Running 대기
    echo "▶ Step 5: 모든 파드 Running 대기..."
    while [[ $(kubectl get pods --no-headers | awk '{print $3}' | grep -v -E 'Running|Completed' | wc -l) -ne 0 ]]; do
      kubectl get pods -o wide
      echo "⏳ 파드 준비 중..."
      sleep 5
    done
    echo "✅ 모든 파드 Running 완료!"

    # 5. uncordon
    echo "▶ Step 4: worker2, worker3 uncordon"
    kubectl uncordon worker2
    kubectl uncordon worker3
    sleep 5



    # ===================================================
    # 모니터링 함수 정의
    # ===================================================
    run_monitor_until_release_stops() {
      local tag=$1
      local proc_name=$2
      local csv_file="node_std_${tag}.csv"

      echo "timestamp,cpu_std" > "$csv_file"
      echo "🟢 nodemonitor.py 실행 중... ($proc_name 종료 시까지)"

      while true; do
        python3 nodemonitor.py >> "$csv_file" 2>/dev/null
        if ! pgrep -f "$proc_name" > /dev/null; then
          echo "🔴 $proc_name 종료 감지 → nodemonitor 중단"
          break
        fi
        sleep 1
      done

      mv "$csv_file" "$RUN_DIR/cpu_std_${tag}.csv"
      echo "📦 CPU 편차 결과 저장 → $RUN_DIR/cpu_std_${tag}.csv"
    }

    # ===================================================
    # 6~7. release1.sh + nodemonitor
    # ===================================================
    echo "▶ Step 6~7: release1.sh + nodemonitor 실행"
    ./release1.sh &
    REL1_PID=$!
    run_monitor_until_release_stops "r1" "release1.sh"
    wait $REL1_PID
    mv result_dynamic.log "$RUN_DIR/result_dynamic_r1.log"

    # 8. 10초 대기
    echo "▶ Step 8: 10초 대기"
    sleep 10

    # ===================================================
    # 9~10. main.py + release2.sh + nodemonitor
    # ===================================================
    echo "▶ Step 9~10: main.py + release2.sh + nodemonitor 실행"
    ./release2.sh "${algo}" &
    REL2_PID=$!

    # nodemonitor는 release2.sh 종료까지 실행
    run_monitor_until_release_stops "r2" "release2.sh"

    # release2.sh 완료 대기
    wait $REL2_PID

    # 결과 로그 이동
    mv result_mainwatch.log "$RUN_DIR/result_mainwatch_r2.log"

    echo "▶ Step 10-1: main.py 종료 후 communication.py 실행"
    python3 communicationcost.py
    if [ -f "communication_cost.csv" ]; then
      mv communication_cost.csv "$RUN_DIR/communication_cost.csv"
      echo "📦 통신 비용 결과 저장 → $RUN_DIR/communication_cost.csv"
    else
      echo "⚠️ communication_cost.csv 파일을 찾을 수 없습니다."
    fi

    # 11. 10초 대기
    echo "▶ Step 11: 10초 대기"
    sleep 10

    # ===================================================
    # 12. release1.sh + nodemonitor 재실행
    # ===================================================
    echo "▶ Step 12: release1.sh + nodemonitor 재실행"
    ./release1.sh &
    REL3_PID=$!
    run_monitor_until_release_stops "r3" "release1.sh"
    wait $REL3_PID
    mv result_dynamic.log "$RUN_DIR/result_dynamic_r3.log"

    # ===================================================
    # 13. mubench 재배포
    # ===================================================
    echo "▶ Step 13: mubench 재배포 (y 자동응답)"
    docker exec -i mubench bash <<'EOF'
yes | python3 Deployers/K8sDeployer/RunK8sDeployer.py -c Configs/K8sParameters.json
exit
EOF

    echo ""
    echo "✅ ${algo} 알고리즘 - 실험 #${run} 완료!"
    echo "📁 결과 저장 경로: ${RUN_DIR}"
    echo "---------------------------------------------------"
  done

  echo ""
  echo "🎯 알고리즘 ${algo}의 ${REPEAT}회 반복 실험 완료!"
  echo "📂 결과 위치: ${ALGO_DIR}"
  echo "==================================================="
done

# ===================================================
# 🔚 전체 종료 요약
# ===================================================
echo ""
echo "🎉 모든 알고리즘 실험 완료!"
echo "📂 전체 결과는 ${SESSION_DIR}에 저장됨"
tree -h "$SESSION_DIR"
