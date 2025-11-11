from kubernetes import client, config
from unit_convertion import cpu_conversion, mem_conversion


def node_capacity_table(core_api: client.CoreV1Api) -> dict:  # 각 노드 별 cpu, mem 총량 
   
    table = {}
    for n in core_api.list_node(watch=False).items:
        name = n.metadata.name
        
        capacity_cpu = cpu_conversion(str(n.status.capacity.get('cpu')))
        capacity_mem =  mem_conversion(str(n.status.capacity.get('memory')))
    
        table[name] = (capacity_cpu, capacity_mem)

    return table    # 노드들의 cpu, mem 총량 table return


def get_nodes_usage(core_api: client.CoreV1Api) -> dict:  # node들의 cpu, mem 사용량 get (%)
   
    metrics_api = client.CustomObjectsApi()
    capacity_table = node_capacity_table(core_api)  # 각 노드 별 cpu, mem 총량 table
    node_res_usage = {} # 각 노드 별 cpu, mem 사용량 저장
    
    try:
        res = metrics_api.list_cluster_custom_object('metrics.k8s.io', 'v1beta1', 'nodes')
        for item in res.get('items', []):
            nodename = item['metadata']['name']
            
            if nodename == 'master':
                continue
            
            node_cpu_usage = cpu_conversion(item['usage']['cpu']) # 각 노드 별 cpu 사용량
            node_mem_usage = mem_conversion(item['usage']['memory'])   # 각 노드 별 mem 사용량
            node_cpu_capacity, node_mem_capacity = capacity_table.get(nodename)
            
            cpu_pct = int(round(node_cpu_usage / node_cpu_capacity * 100)) if node_cpu_capacity else -1 # 각 노드 별 cpu 사용량 (%)
            mem_pct = int(round(node_mem_usage / node_mem_capacity * 100)) if node_mem_capacity else -1 # 각 노드 별 mem 사용량 (%)
            
            node_res_usage[nodename] = (node_cpu_usage, cpu_pct, node_mem_usage, mem_pct, node_cpu_capacity, node_mem_capacity)
    
    except Exception as e:
        print(f"[warn] node metrics 조회 실패: {e}")
    
    return node_res_usage


def get_pods_usage(namespace: str = 'default') -> dict: # 네임스페이스 'default'에 있는 pod들의 cpu, mem 사용량 get
    """
    반환: podname -> (cpu_usage, mem_usage)
    (여러 컨테이너가 있으면 합산)
    """
    metrics_api = client.CustomObjectsApi()
    pod_res_usage = {}  # 각 파드 별 cpu, mem 사용량 저장
    
    try:
        res = metrics_api.list_namespaced_custom_object('metrics.k8s.io', 'v1beta1', namespace, 'pods')
        for item in res.get('items', []):
            podname = item['metadata']['name']
            pod_cpu_usage = 0   # 각 파드 별 cpu 사용량
            pod_mem_usage = 0   # 각 파드 별 mem 사용량
            for c in item.get('containers', []):
                pod_cpu_usage += cpu_conversion(c['usage']['cpu']) 
                pod_mem_usage += mem_conversion(c['usage']['memory'])
            pod_res_usage[podname] = (pod_cpu_usage, pod_mem_usage)
    except Exception as e:
        print(f"[warn] pod metrics 조회 실패(namespace={namespace}): {e}")
        
    return pod_res_usage