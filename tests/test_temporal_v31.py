import time
import sys

def check_temporal_integrity(generated_time_str, system_time):
    # Simulación de la regla Anti-Simulation v3.1
    # Si Jarvis intenta decir que es "Martes" cuando el sistema dice "Lunes"
    if "Tuesday" in generated_time_str and "Mon" in time.ctime(system_time):
        return False, "Temporal Hallucination Detected"
    return True, "Integrity OK"

# Simular fallo previo
res, msg = check_temporal_integrity("Good morning, today is Tuesday 31", time.time())
print(f"Test Result: {res} - {msg}")
