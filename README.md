# Kubernetes-Rescheduling

---

# Communication-Aware Rescheduling (CAR) on Kubernetes

### 📌 프로젝트 개요

이 저장소는 Kubernetes 환경에서의 **Pod 리스케줄링(Rescheduling)** 을 실험하기 위해 구현된
**Communication-Aware Rescheduling (CAR)** 알고리즘과 관련 실험 코드들을 포함합니다.
CAR은 마이크로서비스 간의 **통신 비용(Communication Cost)** 과 **노드 로드 불균형**을 동시에 고려하여
Pod 재배치를 수행함으로써 클러스터의 전체 성능을 향상시키는 것을 목표로 합니다.

---

### ⚙️ 주요 구성

| 폴더/파일              | 설명                                                     |
| ------------------ | ------------------------------------------------------ |
| `main.py` | 리스케줄링 실험의 메인 제어 스크립트.
모든 라운드(round)를 순차적으로 수행하며, podmonitor, harzard_detect, delete_replaced_pod, rescheduling 모듈을 호출하여 노드 모니터링 → 위험 노드 탐지 → 파드 삭제 → 재배치 알고리즘 실행 순으로 진행           |
| `podmonitor.py`   | Kubernetes Metrics API를 통해 노드별 및 파드별 CPU·메모리 사용량을 수집하여, 클러스터 전체의 상태를 딕셔너리(cluster_monitoring)로 구성해 리스케줄러에 전달         |
| `harzard_detect.py` | 모니터링 데이터(cpu_pct)를 기반으로 임계치 이상으로 부하가 걸린 노드를 탐지하고, 그중 CPU 사용률이 가장 높은 노드를 재배치 대상(hazard node) 으로 선정 |
| `delete_replaced_pod.py`   | 과부하 노드에서 가장 CPU 사용량이 높은 파드를 찾아 해당 파드의 Deployment를 삭제 및 재생성할 준비. Pod → ReplicaSet → Deployment 의 소유 관계를 추적하여 Deployment 정보를 추출하고, 삭제 후 Deployment가 완전히 사라질 때까지 대기 |
| `rescheduling.py`          |  실제 재배치 알고리즘(Rescheduling Algorithm)이 구현된 파일. 다음 5가지 알고리즘을 지원합니다:<br>• **spread** – 파드를 가장 적게 가진 노드로 분산 배치<br>• **binpack** – CPU 사용률이 높은 노드로 집중 배치<br>• **random** – 임의의 정상 노드로 재배치<br>• **kubescheduling** – 쿠버네티스 기본 스케줄러 정책 사용<br>• **communication (CAR: Communication-Aware Rescheduling)** – 파드 간 통신 관계를 고려하여, 상호 통신이 많은 파드들을 같은 노드에 재배치하고 통신 비용을 최소화  |
| `workmodelC.json`  | µBench 워크로드 설정 파일 (서비스 토폴로지 및 의존성 정의)                  |
| `auto_full_pipeline_repeat.sh, release1.sh, release2.sh, nodemonitor.py, communicationcost.py` | Kubernetes 클러스터에서 리스케줄링 실험을 자동화하고, 각 단계별 성능 지표를 측정하는 실험 스크립트 세트. 전체 파이프라인은 µBench 워크로드를 배포한 뒤 각 리스케줄링 알고리즘(spread, binpack, random, kubescheduling, communication)을 반복 실행하며, nodemonitor.py로 노드 자원 편차(CPU 표준편차)를 수집하고 communicationcost.py로 통신 비용을 계산. release1.sh와 release2.sh는 부하 테스트를 통해 파드 재스케줄링 전후의 응답시간과 안정성을 측정하고, auto_full_pipeline_repeat.sh는 이 과정을 자동 반복하여 결과를 세션별 디렉터리에 정리|
| `README.md`        | 프로젝트 설명 문서 (본 파일)                                      |

---

### 🧠 알고리즘 개요

**CAR (Communication-Aware Rescheduling)**

* 파드 간 통신 관계를 기반으로 **통신 점수(Communication Score)** 를 계산
* 통신이 많은 Pod들을 동일 노드에 배치하여 **Cross-Node Traffic 감소**
* 노드의 CPU·메모리 사용량을 고려해 **로드 밸런싱 유지**
* Spread, Binpack, Random, Kube-Scheduling 등 기존 기법과 비교 평가

---

### 🧪 실험 환경

* **클러스터 구성:** 1 Control Plane + 3 Worker Nodes
* **Node 사양:** Intel i9-10900K / 32GB RAM / Ubuntu 22.04
* **Kubernetes 버전:** v1.30.14
* **CNI:** Calico (Pod CIDR: 10.244.0.0/16)
* **워크로드:** µBench 마이크로서비스 (s0~s19 구성)
* **모니터링 스택:** kube-prometheus-stack (Prometheus + Grafana + node-exporter)

---

### 📊 실험 지표

| 항목                        | 설명                                         |
| ------------------------- | ------------------------------------------ |
| **Node Load Deviation**   | 노드 간 CPU/Memory 사용량 표준편차 (로드 균형성 측정)       |
| **Average Response Time** | 클라이언트 요청의 평균 응답 시간                         |
| **Communication Cost**    | Pod 간 통신 비용  |

---

### 💻 실행 방법

#### 1️⃣ 리스케줄링 코드 실행

```bash
python3 main.py --algorithm CAR
```

#### 2️⃣ 리스케줄링 실험 전체 자동 반복 실행

```bash
./auto_full_pipeline_repeat.sh

```

---

### 개발 환경

* **언어:** Python 3.12
* **사용 라이브러리:** `kubernetes`, `prometheus-api-client`, `numpy`
* **실험 워크로드:** µBench (IEEE TPDS 2023)

---

### 참고문헌

* A. Detti, L. Funari, L. Petrucci, “µBench: An Open-Source Factory of Benchmark Microservice Applications,” *IEEE TPDS*, 2023.
* A. Marchese, O. Tomarchio, “Load-Aware Container Orchestration on Kubernetes Clusters,” *CLOSER 2024*.
* C. Carrión, “Kubernetes Scheduling: Taxonomy, Ongoing Issues and Challenges,” *ACM Computing Surveys*, 2022.
