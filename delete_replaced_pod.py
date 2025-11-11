from kubernetes import client, config
from get_resource_usage import get_pods_usage  # 파드 CPU/MEM 사용량 조회
from kubernetes.client.rest import ApiException
from kubernetes.client import ApiClient
import time


def wait_deployment_deleted(apps, name: str, ns: str, timeout=180, interval=1.5) -> bool:
    """Deployment가 완전히 사라질 때(404)까지 대기."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            d = apps.read_namespaced_deployment(name=name, namespace=ns)
            # 아직 남아있음(삭제중). 필요하면 상태 로그:
            # print(f"deleting... deletionTimestamp={d.metadata.deletion_timestamp}")
        except ApiException as e:
            if e.status == 404:
                return True  # 이름 해제 완료
            else:
                raise
        time.sleep(interval)
    return False

# Pod -> ReplicaSet -> Deployment 역추적
def deployment_for_pod(apps_v1: client.AppsV1Api, namespace, dpod):

    owners = (dpod.metadata.owner_references or [])

    for o in owners:    # Pod가 Deployment의 직접 소유일 때,
        if o.kind == "Deployment":
            return o.name
        elif o.kind == 'ReplicaSet':    # 일반적으로 Pod -> ReplicaSet -> Deployment 구조
            rs = apps_v1.read_namespaced_replica_set(o.name, namespace) # ReplicaSet 객체
            rs_owners = (rs.metadata.owner_references or [])
            for ro in rs_owners:
                if ro.kind == "Deployment": # 해당 ReplicaSet을 소유가 Deployment
                    return ro.name  # Deployment 이름 return
    return None

# CPU 최댓값 파드 선택
def pick_max_pod(most_harzard, spods, pod_res_usage):

    maxpod = None
    maxpod_cpu_usage = -1
    maxpod_mem_usage = 0

    for p in spods:
        if p.spec.node_name != most_harzard:
            continue

        podname = p.metadata.name
        pod_cpu_usage, pod_mem_usage = pod_res_usage.get(podname, ("0", "0"))   #해당 파드의 cpu, mem 사용량 가져오기

        if pod_cpu_usage > maxpod_cpu_usage:
            maxpod = p
            maxpod_cpu_usage = pod_cpu_usage
            maxpod_mem_usage = pod_mem_usage

    if maxpod is None:
        return None
    return maxpod   # return


def extract_deployment_info(dep: client.V1Deployment): 
    
    api = ApiClient()
    
    meta = dep.metadata or client.V1ObjectMeta()
    spec = dep.spec or client.V1DeploymentSpec() 
    tmpl = (spec.template or client.V1PodTemplateSpec()) 
    tmpl_meta = tmpl.metadata or client.V1ObjectMeta() 
    tmpl_spec = tmpl.spec or client.V1PodSpec() 
    selector = spec.selector or client.V1LabelSelector() 
    strategy = spec.strategy or client.V1DeploymentStrategy() 
    

    containers_info = [] 
    
    for c_ori in (tmpl_spec.containers or []): 
        
        c_dict = api.sanitize_for_serialization(c_ori)
        
        keep = ["name", 'image', 'imagePullPolicy', 'ports', 'env', 'resources', 'volumeMounts']
        c = {key: value for key, value in c_dict.items() if key in keep}
        
        c["imagePullPolicy"] = "IfNotPresent"
        
        containers_info.append(c)
        
        # containers_info.append({
            
        #     "name": c.name,
        #     "image": c.image,
        #     "imagePullPolicy": c.image_pull_policy,
        #     "ports": [
        #         {
        #             "name": p.name,
        #             "containerPort": p.container_port,
        #             "protocol": p.protocol
        #         } for p in (c.ports or [])
        #     ],
        #     "env": [e.to_dict() for e in (c.env or [])] if hasattr(c, "env") else None,
        #     "resources": {
        #         "requests": (c.resources.requests if c.resources and c.resources.requests else None),
        #         "limits":   (c.resources.limits   if c.resources and c.resources.limits   else None),
        #     },
        #     "volumeMounts": [vm.to_dict() for vm in (c.volume_mounts or [])] if hasattr(c, "volume_mounts") else None
        #     }
        # ) 
        
    volumes = [api.sanitize_for_serialization(v) for v in (tmpl_spec.volumes or [])] or None
    strategy_dict = api.sanitize_for_serialization(strategy) if strategy else None
    affinity_dict = api.sanitize_for_serialization(tmpl_spec.affinity) if getattr(tmpl_spec, "affinity", None) else None
        
    info = {"apiVersion": dep.api_version, 
            "kind": dep.kind, 
            "metadata": { "name": meta.name, 
                         "namespace": meta.namespace, 
                         "labels": dict(meta.labels or {}) }, 
            "spec": { "replicas": spec.replicas, 
                     "selector": { "matchLabels": dict(selector.match_labels or {}), 
                                  "matchExpressions": [me.to_dict() for me in (selector.match_expressions or [])] if hasattr(selector, "match_expressions") else None, }, 
                     "strategy": strategy_dict,
                     "template": { "metadata": { "labels": dict(tmpl_meta.labels or {}), 
                                                "annotations": dict(tmpl_meta.annotations or {}), }, 
                                  "spec": { 
                                           "containers": containers_info, 
                                           "volumes": volumes,
                                           "restartPolicy": "Always",
                                           "terminationGracePeriodSeconds": tmpl_spec.termination_grace_period_seconds,
                                           "dnsPolicy": "ClusterFirst",
                                           "nodeSelector": dict(tmpl_spec.node_selector or {}) if tmpl_spec.node_selector else None, 
                                           "affinity": affinity_dict,
                                           "schedulerName": "default-scheduler"
                                           } 
                                  } 
                     } 
            } 
    
    info = api.sanitize_for_serialization(info)
    
    return info

def pod_delete(most_harzard, spods,namespace, relation):  # most_harzard에 포함된 파드 삭제

    config.load_kube_config()
    apps_v1 = client.AppsV1Api()

    # pods의 cpu, mem 사용량
    pod_res_usage = get_pods_usage('default')

    
    # most_harzard 노드 중 CPU 사용량이 최대인 pod 선택
    picked = pick_max_pod(most_harzard, spods, pod_res_usage)
    
    
    if picked is None:
        print(f"[delete] Node '{most_harzard}' 에 적합한 파드가 없습니다.")
        return None

    dpod = picked # 삭제될 파드 객체, cpu , mem 사용량
    dpodname = dpod.metadata.name
    deployment_name = deployment_for_pod(apps_v1, namespace, dpod)
    
    deployment_info = {}

    try:
            
        deployment = apps_v1.read_namespaced_deployment(name=deployment_name, namespace=namespace)
        deployment_info = extract_deployment_info(deployment)
            
            
        body = client.V1DeleteOptions(propagation_policy="Foreground")
        apps_v1.delete_namespaced_deployment(name=deployment_name, namespace=namespace, body=body)
        print(f"[delete] Deleted Deployment {deployment_name} (ns={namespace}); pod {dpodname}.")
        
        ok = wait_deployment_deleted(apps_v1, deployment_name, namespace, timeout=180, interval=1.5)
        if not ok:
            print(f"[delete][warn] {deployment_name} 삭제 대기 타임아웃 → 이번 라운드 스킵")
            return None  # main에서 스킵되게 함
    
    except Exception as e:
        print(f"[delete][warn] 삭제 중 오류: {type(e).__name__}: {e}")

    return deployment_info, dpodname
