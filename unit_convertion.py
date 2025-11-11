def cpu_conversion(cpu_usage: str) -> int:  # milicore 단위 변환 ex) 53m -> 54
   
    s = str(cpu_usage).strip()
    if s.endswith('m'):
        return int(float(s[:-1]))
    elif s.endswith('n'):  # ← 추가
        # 1,000,000n = 1m
        return int(round(float(s[:-1]) / 1_000_000))
    elif s.endswith('u'):
        return int(round(float(s[:-1])/ 1000))

    
    return int(round(float(s) * 1000)) 
   
def mem_conversion(mem_usage: str) -> int: # '536Mi' -> bytes

    s = str(mem_usage).strip()
    units = {
        'Ki': 1024,
        'Mi': 1024**2,
        'Gi': 1024**3,
        'Ti': 1024**4,
        'Pi': 1024**5,
        'Ei': 1024**6
    }
    
    unit = s[-2:]
    
    if unit in units:
        return int(float(s[:-len(unit)]) * units[unit])
    
    return int(float(s))    # 단위 안붙어있을 때 숫자 return


def _format_millicores(m: int) -> str:
    return f"{int(m)}m"

def _format_bytes_as_mi(b: int) -> str:
    return f"{int(round(b / (1024*1024)))}Mi"