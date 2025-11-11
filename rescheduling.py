from __future__ import annotations
from kubernetes import client, config
from kubernetes.client import ApiException
import copy
import random as rd
import time

def _wait_deleted(apps_v1: client.AppsV1Api, namespace: str, name: str, timeout: int = 120) -> bool:
    start = time.time()
    while time.time() - start < timeout:
        try:
            apps_v1.read_namespaced_deployment(name=name, namespace=namespace)
        except ApiException as e:
            if e.status == 404:
                return True
            else:
                raise
        time.sleep(1)
    return False

def _merge_affinity(orig, patch):
   
    o = copy.deepcopy(orig) if orig else {}
    for k, v in patch.items():
        if k not in o or not isinstance(o.get(k), dict) or not isinstance(v, dict):
            o[k] = v
            continue
        # both dicts
        for kk, vv in v.items():
            if kk not in o[k]:
                o[k][kk] = vv
            elif isinstance(vv, dict) and isinstance(o[k][kk], dict):
                for kkk, vvv in vv.items():
                    if isinstance(vvv, list) and isinstance(o[k][kk].get(kkk), list):
                        o[k][kk][kkk].extend(vvv)
                    else:
                        o[k][kk][kkk] = vvv
            else:
                o[k][kk] = vv
    return o

def exclude_hazard_nodes(hazard_nodes):
    return {
        'nodeAffinity': {
            'requiredDuringSchedulingIgnoredDuringExecution': {
                'nodeSelectorTerms': [{
                    'matchExpressions': [{
                        'key': 'kubernetes.io/hostname',
                        'operator': 'NotIn',
                        'values': hazard_nodes
                    }]
                }]
            }
        }
    }

def create(apps_v1: client.AppsV1Api, namespace, body, wait_if_exists: bool = False):
    
    name = body['metadata']['name']
    if wait_if_exists:
        _wait_deleted(apps_v1, namespace, name)
    try:
        # NOTE: pass dict directly; the client accepts dict bodies
        apps_v1.create_namespaced_deployment(namespace=namespace, body=body)
        print(f"[success] New Deployment {name} created in ns={namespace}.")
        return True
    except ApiException as e:
        print(f"[error] create {name}: {e.status} {e.reason}")
        try:
            print(e.body)
        except Exception:
            pass
        return False



def spread(deployment_info, harzard_node, cluster_monitoring):

    config.load_kube_config()
    
    apps_v1 = client.AppsV1Api()

    namespace = deployment_info['metadata'].get('namespace', 'default')

    base_affinity = deployment_info['spec']['template']['spec']['affinity']
    patch = exclude_hazard_nodes(harzard_node)
    deployment_info['spec']['template']['spec']['affinity'] = _merge_affinity(base_affinity, patch)
    
    othernode = {}    
    
    for nodename, nodeinfo in cluster_monitoring.items():
        if nodename in harzard_node:
            continue
        
        podcnt = len(nodeinfo['pods'])
        othernode[nodename] = podcnt
    
    if not othernode:
        raise RuntimeError("No candidate nodes available (all nodes are hazardous).")
    
    minnode, mincnt = min(othernode.items(), key=lambda item: (item[1], item[0]))
    
    deployment_info['spec']['template']['spec']['nodeSelector'] = {'kubernetes.io/hostname': minnode}

    return create(apps_v1, namespace, deployment_info)

def binpack(deployment_info, harzard_node, cluster_monitoring):
    
    config.load_kube_config()
    
    apps_v1 = client.AppsV1Api()

    namespace = deployment_info['metadata'].get('namespace', 'default')


    base_affinity = deployment_info['spec']['template']['spec']['affinity']
    patch = exclude_hazard_nodes(harzard_node)
    deployment_info['spec']['template']['spec']['affinity'] = _merge_affinity(base_affinity, patch)


    othernode = {}
    
    for nodename, nodeinfo in cluster_monitoring.items():
        if nodename in harzard_node:
            continue
        
        podusage = nodeinfo['cpu_pct']
        othernode[nodename] = podusage
        
    if not othernode:
        raise RuntimeError("No candidate nodes available (all nodes are hazardous).")
        
    maxnode, maxusage = max(othernode.items(), key=lambda item: (item[1], item[0]))
        
    deployment_info['spec']['template']['spec']['nodeSelector'] = {'kubernetes.io/hostname': maxnode}
        
    return create(apps_v1, namespace, deployment_info)


def random(deployment_info, harzard_node, nodes_name):
    
    config.load_kube_config()

    apps_v1 = client.AppsV1Api()

    namespace = deployment_info['metadata'].get('namespace', 'default')


    candidates = [n for n in nodes_name if n not in harzard_node]
    
    if not candidates:
        raise RuntimeError("No candidate nodes available (all nodes are hazardous).")
    target = rd.choice(candidates)

    deployment_info['spec']['template']['spec']['nodeName'] = target

    return create(apps_v1, namespace, deployment_info)

def kubescheduling(deployment_info, harzard_node):
    
    config.load_kube_config()

    apps_v1 = client.AppsV1Api()

    namespace = deployment_info['metadata'].get('namespace', 'default')

    base_affinity = deployment_info['spec']['template']['spec']['affinity']
    patch = exclude_hazard_nodes(harzard_node)
    deployment_info['spec']['template']['spec']['affinity'] = _merge_affinity(base_affinity, patch)

    return create(apps_v1, namespace, deployment_info)


def communication(deployment_info, harzard_node, cluster_monitoring, relations, nodes_name):
    config.load_kube_config()
    apps_v1 = client.AppsV1Api()
    namespace = deployment_info['metadata'].get('namespace', 'default')
    
    base_affinity = deployment_info['spec']['template']['spec']['affinity']
    patch = exclude_hazard_nodes(harzard_node)
    deployment_info['spec']['template']['spec']['affinity'] = _merge_affinity(base_affinity, patch)
    
    name = deployment_info['metadata']['name']  #   name = 's0'
    rel = relations.get(name, [])    #  rel = ['s1','s16','s3','s7']
    score = {}
    target = None
    
    for workername in nodes_name:
        if workername in harzard_node:  #   harzard node면 pass
            continue
        
        score[workername] = 0
        for pod in cluster_monitoring[workername]['pods']:
            if pod['deploymentname'] in rel:
                score[workername] +=1
                
    # harzard 노드를 제외하고 가장 높은 score를 가진 노드에 배치, 만일 score가 같다면 잔여 용량이 가장 큰 노드에 배치
        
    max_score = max(score.values())
    best_nodes = [node for node, s in score.items() if s == max_score]

    if len(best_nodes) > 1:
        max_remaining_cpu = -1
                    
        for node in best_nodes:
            cpu_capacity = cluster_monitoring[node]['node_cpu_capacity']
            cpu_usage = cluster_monitoring[node]['node_cpu_usage']
            remaining_cpu = cpu_capacity - cpu_usage
                
            if remaining_cpu > max_remaining_cpu:
                max_remaining_cpu = remaining_cpu
                target = node
    else:
        target = best_nodes[0]  
    
    deployment_info['spec']['template']['spec']['nodeName'] = target
    
    return create(apps_v1, namespace, deployment_info)

