import random


class ABTestManager:
    def __init__(self):
        self.prompt_versions: dict[str, str] = {}

    def pick_prompt_version(self, trip_id) -> str:
        tid = str(trip_id)
        if tid not in self.prompt_versions:
            self.prompt_versions[tid] = random.choice(["v1", "v2"])
        return self.prompt_versions[tid]
