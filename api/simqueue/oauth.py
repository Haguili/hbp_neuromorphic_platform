import logging
import requests
import json
from authlib.integrations.starlette_client import OAuth
from fastapi import HTTPException, status


from . import settings

logger = logging.getLogger("simqueue")

oauth = OAuth()

oauth.register(
    name="ebrains",
    server_metadata_url=settings.EBRAINS_IAM_CONF_URL,
    client_id=settings.EBRAINS_IAM_CLIENT_ID,
    client_secret=settings.EBRAINS_IAM_SECRET,
    userinfo_endpoint=f"{settings.HBP_IDENTITY_SERVICE_URL}/userinfo",
    client_kwargs={
        "scope": "openid profile collab.drive clb.drive:read clb.drive:write group team web-origins roles email",
        "trust_env": False,
    },
)


async def get_collab_info(collab_id, token):
    collab_info_url = f"{settings.HBP_COLLAB_SERVICE_URL_V2}collabs/{collab_id}"
    headers = {"Authorization": f"Bearer {token}"}
    res = requests.get(collab_info_url, headers=headers)
    try:
        response = res.json()
    except json.decoder.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid collab id"
        )
    return response


class User:

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @classmethod
    async def from_token(cls, token):
        user_info = await oauth.ebrains.userinfo(
            token={"access_token": token, "token_type": "bearer"}
        )
        return cls(**user_info)

    @property
    def is_admin(self):
        return False

    @property
    def username(self):
        return self.preferred_username

    async def can_view(self, collab_id):
        # first of all, check team permissions
        target_team_names = {role: f"collab-{collab_id}-{role}"
                             for role in ("viewer", "editor", "administrator")}
        for role, team_name in target_team_names.items():
            if team_name in self.roles["team"]:
                return True
        # if that fails, check if it's a public collab
        collab_info = await get_collab_info(collab_id, self.token["access_token"])
        return collab_info.get("isPublic", False)

    def can_edit(self, collab_id):
        target_team_names = {role: f"collab-{collab_id}-{role}"
                             for role in ("editor", "administrator")}
        for role, team_name in target_team_names.items():
            if team_name in self.roles["team"]:
                return True
