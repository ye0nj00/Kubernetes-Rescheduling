from kubernetes import client, config
from get_resource_usage import get_nodes_usage, get_pods_usage
from unit_convertion import _format_millicores, _format_bytes_as_mi
from delete_replaced_pod import deployment_for_pod


def monitor():
    #list all pods:

    # Configs can be set in Configuration class directly or using helper utility
    config.load_kube_config()

    v1 = client.CoreV1Api()
    apps_v1 = client.AppsV1Api()
    cluster_monitoring = {} # 모니터링 dict

    # cluster_monitoring = {
    #         "<nodeName>": {
    #                 "node_cpu_capacity": node_cpu_capacity,
    #                 "node_cpu_usage": node_cpu_usage,
    #                 "cpu_pct": cpu_pct,
    #
    #                 "node_mem_capacity": node_mem_capacity,
    #                 "node_mem_usage": node_mem_usage, 
    #                 "mem_pct": mem_pct
    #                     "pods": [
    #                 {
    #                     "namespace": "default",
    #                     "name": "nginx-123",
    #                     "cpu_cores": 0.05,        # 파드 CPU (cores)
    #                     "memory_bytes": 12_345_678 # 파드 메모리 (bytes)
    #                 },
    #                 # ...
    #             ]
    #         },
    #         # ...
    # }



    #######################################################


    nodes = v1.list_node(watch=False)  
    nodes_name = [i.metadata.name for i in nodes.items if i.metadata.name != 'master'] # node 이름 리스트 출력
    
    
    
    
    print("[node list:]")

    for name in nodes_name:
        print(name)
        if name == 'master':
            continue
        cluster_monitoring[name] = {}  


    print("\n[node utilization:]")  # node cpu, mem 사용량 모니터링
    node_res_usage = get_nodes_usage(v1)
    if node_res_usage:
        print("NAME\tCPU capacity(cores)\tCPU(cores)\tCPU%\tMEMORY capacity(bytes)\tMEMORY(bytes)\tMEMORY%")
        for name in nodes_name:
            
            if name == 'master':
                continue
            
            if name in node_res_usage:
                node_cpu_usage, cpu_pct, node_mem_usage, mem_pct, node_cpu_capacity, node_mem_capacity = node_res_usage[name]
                print(f"{name}\t{_format_millicores(node_cpu_capacity)}\t{_format_millicores(node_cpu_usage)}\t{cpu_pct}\t{_format_millicores(node_mem_capacity)}\t{_format_bytes_as_mi(node_mem_usage)}\t{mem_pct}")
            
                cluster_monitoring[name] = {
                
                    "node_cpu_capacity": node_cpu_capacity,
                    "node_cpu_usage": node_cpu_usage,
                    "cpu_pct": cpu_pct,

                    "node_mem_capacity": node_mem_capacity,
                    "node_mem_usage": node_mem_usage, 
                    "mem_pct": mem_pct,
                
                    "pods": []
                
                }
            
    else:
        print("metrics-server 가 없거나 metrics.k8s.io API를 조회할 수 없습니다.")


########################################################

    pods = v1.list_pod_for_all_namespaces(watch=False)
    spods = [spod for spod in pods.items if spod.metadata.namespace == 'default']   # default 네임스페이스에 있는 pods

    for node_name in nodes_name:
    
        if node_name == 'master':
            continue
    
        print(f"list of pods on node {node_name}")
    
        pod_res_usage = get_pods_usage('default')

        for p in spods:
            if p.spec.node_name == node_name:
            
                if pod_res_usage:
                
                    podname = p.metadata.name
                    pod_cpu_usage, pod_mem_usage = pod_res_usage.get(podname, ("-", "-"))
                    deployment_name = deployment_for_pod(apps_v1, 'default', p)
                    
                    print(f"{p.status.pod_ip}\t{p.metadata.namespace}\t{podname}\t{p.spec.node_name}\t{deployment_name}\t{pod_cpu_usage}\t{pod_mem_usage}")
                    cluster_monitoring[p.spec.node_name]["pods"].append({
                    
                        'podname': podname,
                        'deploymentname': deployment_name, 
                        'pod_cpu_usage': pod_cpu_usage,
                        "pod_mem_usage": pod_mem_usage
                    
                    })
                
                else:
                    print("%s\t%s\t%s\t%s\tmetrics-server 가 없거나 metrics.k8s.io API를 조회할 수 없습니다." % (p.status.pod_ip, p.metadata.namespace, p.metadata.name, p.spec.node_name))
    return nodes_name, spods,cluster_monitoring
    
#########################################################


if __name__ == "__main__":
    nodes_name, spods, cluster_monitoring = monitor()
    print(nodes_name)
    print(cluster_monitoring)