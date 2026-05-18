from config import GEOREF_METHOD
from georef.methods import helmert


METHODS = {
    "helmert": helmert.estimate_transform,
}


def get_method(method_name=GEOREF_METHOD):
    try:
        return METHODS[method_name]
    except KeyError as exc:
        available = ", ".join(sorted(METHODS))
        raise ValueError(
            f"Methode de georeferencement inconnue : {method_name}. "
            f"Disponibles : {available}"
        ) from exc
