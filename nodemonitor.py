from kubernetes import client, config
import numpy
import os
import csv
from datetime import datetime
from unit_convertion import cpu_conversion, mem_conversion
from get_resource_usage import node_capacity_table

def node_resorce_std():
    
    config.load_kube_config()
    core_api = client.CoreV1Api()
    metrics_api = client.CustomObjectsApi()
    
    node_cpu_usagep = []
    
    
    try:
        
        capacity_table = node_capacity_table(core_api)
        res = metrics_api.list_cluster_custom_object('metrics.k8s.io', 'v1beta1', 'nodes')
        
        
        for item in res.get('items', []):
            nodename = item['metadata']['name']
            
            if nodename == 'master':
                continue
            
            if nodename not in capacity_table:
                print(f"[warn] 노드 '{nodename}'의 용량 정보를 찾을 수 없어 건너뜁니다.")
                continue
            
            cpu_capacity, _ = capacity_table[nodename]
            node_cpu_usage = cpu_conversion(item['usage']['cpu']) # 각 노드 별 cpu 사용량
            
            if cpu_capacity > 0:
                # (현재 사용량 / 총 용량) * 100
                cpu_usage_percent = (node_cpu_usage / cpu_capacity) * 100
                node_cpu_usagep.append(cpu_usage_percent)
            else:
                # 용량이 0인 경우는 계산에서 제외
                print(f"[warn] 노드 '{nodename}'의 CPU 용량이 0이어서 건너뜁니다.")
            
        if node_cpu_usagep:
            cpu_std_percent = numpy.std(node_cpu_usagep)
            
            #CPU 사용률의 표준편차만 반환
            return cpu_std_percent 
        else:
            # 계산할 데이터가 없는 경우
            return 0.0    
        
    except Exception as e:
        print(f"[warn] node metrics 조회/계산 실패: {e}")
        return None


def save_to_csv(cpu_std, filename="node_std.csv"):
    """
    CSV 파일에 타임스탬프와 함께 표준편차 값 저장
    """
    file_exists = os.path.isfile(filename)
    
    with open(filename, 'a', newline='') as f:
        writer = csv.writer(f)
        
        # 파일이 새로 생성될 때 헤더를 작성
        if not file_exists:
            writer.writerow(['timestamp', 'cpu_std'])
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        writer.writerow([timestamp, cpu_std])



if __name__ == "__main__":
    cpu_std = node_resorce_std()
    
    if cpu_std != None:
        print(f"CPU 표준편차: {cpu_std:.2f}")
        save_to_csv(cpu_std)
    else:
        print("데이터 수집 및 저장 실패")
    