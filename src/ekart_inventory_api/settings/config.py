import os

from dynaconf import Dynaconf, Validator  # type: ignore

current_directory = os.path.dirname(os.path.realpath(__file__))

settings = Dynaconf(
    envvar_prefix=False,
    settings_files=[
        f"{current_directory}/settings.toml",
        f"{current_directory}/.secrets.toml",
    ],
    load_dotenv=True,
    environments=True,
)

settings.validators.register(
    Validator("DB_PORT", cast=str), Validator("PGPORT", cast=str)
)
