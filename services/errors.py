class MadameRillionaError(RuntimeError):
    """Erreur métier générale du bot."""


class DuplicateArchetypeError(MadameRillionaError):
    pass


class ArchetypeNotFoundError(MadameRillionaError):
    pass


class DuplicateComboError(MadameRillionaError):
    pass


class ComboNotFoundError(MadameRillionaError):
    pass


class InvalidComboError(MadameRillionaError):
    pass
