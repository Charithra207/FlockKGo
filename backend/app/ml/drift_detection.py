import numpy as np


def detect_preference_drift(current_vectors, previous_vectors) -> dict:
    details = {}
    distances = []
    for pid, current in current_vectors.items():
        previous = previous_vectors.get(pid)
        if not previous:
            details[str(pid)] = {"distance": 0.0, "status": "stable"}
            continue
        distance = float(np.linalg.norm(np.array(current) - np.array(previous)))
        distances.append(distance)
        status = "stable" if distance < 0.2 else "minor_drift" if distance <= 0.5 else "significant_drift"
        details[str(pid)] = {"distance": distance, "status": status}

    average = float(np.mean(distances)) if distances else 0.0
    group_stability = "stable" if average < 0.2 else "minor_drift" if average <= 0.5 else "significant_drift"
    return {
        "participants": details,
        "group_stability": group_stability,
        "average_drift": average,
        "action_needed": group_stability == "significant_drift",
    }
