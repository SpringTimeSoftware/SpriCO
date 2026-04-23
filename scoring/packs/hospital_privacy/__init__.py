"""Hospital privacy policy pack for SpriCO scoring."""

__all__ = ["HospitalPrivacyCompositeScorer"]


def __getattr__(name: str):
    if name == "HospitalPrivacyCompositeScorer":
        from scoring.packs.hospital_privacy.scorer import HospitalPrivacyCompositeScorer

        return HospitalPrivacyCompositeScorer
    raise AttributeError(name)
