from get_resource_usage import get_nodes_usage

def detection(node_name, cluster_monitoring):
    
    harzard_nodes = []
    most_harzard = ''
    threshold = 30 # 안전 임계치
    
    for nodename in node_name:  # 각 노드의 cpu(%) 사용량 중 하나가 임계치를 넘으면 위험 노드로 설정
        status = cluster_monitoring.get(nodename, {}) 
        
        if (status['cpu_pct'] >= threshold):
            harzard_nodes.append(nodename)
    
    
    if harzard_nodes:
        h_avr = {}
    
        for nodename in harzard_nodes: 
            status = cluster_monitoring.get(nodename, {})
            pct = status['cpu_pct']
            h_avr[nodename] = pct    
        
        most_harzard = max(h_avr, key = h_avr.get)  # 위험 노드 중 cpu(%)가 가장 높은 node를 재배치가 필요한 노드로 선정 
           
    
    return most_harzard, harzard_nodes