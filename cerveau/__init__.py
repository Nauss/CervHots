"""Le cerveau du coach : hotstate + savoir → décision de parole."""
# Les outils hors ligne ne doivent pas charger le client API du Coach.
__all__ = ["Coach", "Decision"]


def __getattr__(name):
    if name in __all__:
        from .brain import Coach, Decision
        return {"Coach": Coach, "Decision": Decision}[name]
    raise AttributeError(name)
