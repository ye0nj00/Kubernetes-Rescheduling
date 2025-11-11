import time
import sys
from datetime import datetime
from podmonitor import monitor
from harzard_detect import detection
from delete_replaced_pod import pod_delete
from rescheduling import spread, binpack, random, kubescheduling, communication


def edit_cluster(cluster, dpodname, most_harzard):
    pods = cluster[most_harzard]['pods']
    n = 0
    for podinfo in pods:
        if podinfo['podname'] is not dpodname:
            n += 1
            continue
        del cluster[most_harzard]['pods'][n]
        break
    return cluster


def main(algorithm_name: str):
    """
    algorithm_name: 'spread' | 'binpack' | 'random' | 'kubescheduling' | 'communication'
    """

    SLEEP_AFTER_ACTION = 15
    MAX_ROUNDS = 10
    round_num = 1

    relation = {
        's0': ["s1", "s3", "s7", "s16"],
        's1': ["s0", "s2", "s4", "s13", "s15"],
        's2': ['s1'],
        's3': ["s0", "s5", "s6", "s8", "s9", "s12"],
        's4': ['s1'],
        's5': ["s3", "s14"],
        's6': ["s3", "s10", "s17"],
        's7': ["s0", "s19"],
        's8': ['s3'],
        's9': ["s3", "s11"],
        's10': ["s6"],
        's11': ["s9"],
        's12': ["s3"],
        's13': ["s1"],
        's14': ["s5"],
        's15': ["s1", "s18"],
        's16': ["s0"],
        's17': ["s6"],
        's18': ["s15"],
        's19': ["s7"]
    }

    print(f"[info] 선택된 재스케줄링 알고리즘: {algorithm_name}")

    while round_num <= MAX_ROUNDS:
        print(f"\n[round {round_num}] monitoring...")
        nodes_name, spods, cluster_monitoring = monitor()

        most_harzard, harzard_node = detection(nodes_name, cluster_monitoring)

        if most_harzard:
            print(f"[round {round_num}] most_harzard={most_harzard}, harzard_node={harzard_node}")

            deployment_info, dpodname = pod_delete(
                most_harzard,
                spods,
                'default',
                relation
            )

            if deployment_info:
                cluster_monitoring = edit_cluster(cluster_monitoring, dpodname, most_harzard)
                try:
                    print(f"[round {round_num}] {algorithm_name} 적용 중...")

                    # 선택된 알고리즘 실행
                    if algorithm_name == "spread":
                        spread(deployment_info, harzard_node, cluster_monitoring)

                    elif algorithm_name == "binpack":
                        binpack(deployment_info, harzard_node, cluster_monitoring)

                    elif algorithm_name == "random":
                        random(deployment_info, harzard_node, nodes_name)

                    elif algorithm_name == "kubescheduling":
                        kubescheduling(deployment_info, harzard_node)

                    elif algorithm_name == "communication":
                        communication(deployment_info, harzard_node, cluster_monitoring, relation, nodes_name)

                    else:
                        print(f"[error] 지원되지 않는 알고리즘 이름: {algorithm_name}")
                        break

                except Exception as e:
                    print(f"[error] 재배치 중 예외 발생: {e}")

                time.sleep(SLEEP_AFTER_ACTION)
                round_num += 1

            else:
                print("[warn] deployment_info를 얻지 못해 재배치를 스킵합니다.")
                time.sleep(SLEEP_AFTER_ACTION)
                round_num += 1
                continue

        else:
            print("[info] 모든 노드가 안정 상태입니다.")
            time.sleep(SLEEP_AFTER_ACTION)
            round_num += 1

    if round_num > MAX_ROUNDS:
        print(f"[stop] MAX_ROUNDS({MAX_ROUNDS}) 도달로 종료합니다.")


if __name__ == "__main__":
    # 명령행 인자에서 알고리즘 이름 읽기
    if len(sys.argv) < 2:
        print("사용법: python3 main.py [algorithm_name]")
        print("예시: python3 main.py spread")
        sys.exit(1)

    algorithm_name = sys.argv[1].strip().lower()
    start_time = time.time()

    main(algorithm_name)

    end_time = time.time()
    duration = end_time - start_time

    print(f"\nmain.py 시작 시간: {datetime.fromtimestamp(start_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"main.py 종료 시간: {datetime.fromtimestamp(end_time).strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"main.py 전체 소요 시간: {duration:.2f} 초")
