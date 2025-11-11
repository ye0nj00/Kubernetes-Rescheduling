from kubernetes import config, client
from datetime import datetime
import os
import csv

def communication_cost(relation):
    
    #relation: {'s0': ['s1','s16','s3','s7'], 's1': ['s0','s13','s15','s2','s4'], ...}
    
    config.load_kube_config()
    
    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    
    cost = 0
    inf = {}
    
    try:
        pods = v1.list_pod_for_all_namespaces(watch=False)
        spods = [spod for spod in pods.items if spod.metadata.namespace == 'default']   # default 네임스페이스에 있는 pods  
    
        for pod in spods:
            
            node_name = pod.spec.node_name
            owners = (pod.metadata.owner_references or [])

            for o in owners:    # Pod가 Deployment의 직접 소유일 때,
                if o.kind == "Deployment":
                    deployment_name = o.name
                elif o.kind == 'ReplicaSet':    # 일반적으로 Pod -> ReplicaSet -> Deployment 구조
                    rs = apps_v1.read_namespaced_replica_set(o.name, 'default') # ReplicaSet 객체
                    rs_owners = (rs.metadata.owner_references or [])
                    for ro in rs_owners:
                        if ro.kind == "Deployment": # 해당 ReplicaSet을 소유가 Deployment
                            deployment_name = ro.name  # Deployment 이름 return
        
            inf[deployment_name] = node_name
        
        
        for dep, node in inf.items():
            for rel in relation.get(dep, []):
                if node != inf.get(rel):
                    cost +=1
    
        return cost/2  
    
    except Exception as e:
        print(f"[ERROR] 통신 비용 계산 중 오류 발생: {e}")
        return -1
    

def save_to_csv(cost, filename="communication_cost.csv"):
    
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # 파일이 새로 생성될 때 헤더를 작성
        if not file_exists:
            writer.writerow(['timestamp', 'cost'])
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([timestamp, cost])


if __name__ == "__main__":
    
    relation = {'s0': ["s1", "s3", "s7", "s16"],
                        's1': ["s0", "s2", "s4", "s13", "s15"],
                        's2': ['s1'],
                        's3': ["s0","s5", "s6", "s8", "s9", "s12"],
                        's4': ['s1'],
                        's5': ["s3","s14"],
                        's6': ["s3","s10", "s17"],
                        's7': ["s0","s19"],
                        's8': ['s3'],
                        's9': ["s3", "s11"],
                        's10': ["s6"],
                        's11': ["s9"],
                        's12': ["s3"],
                        's13': ["s1"],
                        's14': ["s5"],
                        's15': ["s1","s18"],
                        's16': ["s0"],
                        's17': ["s6"],
                        's18': ["s15"],
                        's19': ["s7"]}
    cost = communication_cost(relation)
    
    if cost != -1:
        save_to_csv(cost)
        print("통신 비용:", cost)
    else:
        print("데이터 수집 및 저장 실패")
        