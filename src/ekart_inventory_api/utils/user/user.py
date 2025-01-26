from .core.constants.user_enums import UserAccess


def get_overall_user_access_score(access_roles: list[str] = None) -> str:
    if not access_roles:
        return ""
    total_access_value = sum(
        int(UserAccess[role.upper()].value, 16) for role in access_roles
    )
    return total_access_value


def decode_user_access(user_access_score: str | None) -> list[str]:
    if not user_access_score:
        return []

    access_score = int(user_access_score, 16)

    return [
        access.name.lower()
        for access in UserAccess
        if access_score & int(access.value, 16) == int(access.value, 16)
    ]
