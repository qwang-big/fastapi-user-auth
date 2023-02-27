from typing import Type

from fastapi import FastAPI
from fastapi_amis_admin.admin import AdminSite, PageSchemaAdmin, Settings
from fastapi_amis_admin.amis.components import ActionType, App, Dialog, Flex, Service
from fastapi_amis_admin.amis.constants import SizeEnum
from fastapi_amis_admin.amis.types import AmisAPI
from fastapi_amis_admin.crud.utils import SqlalchemyDatabase
from fastapi_amis_admin.utils.translation import i18n as _
from starlette.requests import Request

from fastapi_user_auth.admin import CasbinRuleAdmin
from fastapi_user_auth.app import UserAuthApp as DefaultUserAuthApp
from fastapi_user_auth.auth import Auth
from fastapi_user_auth.auth.schemas import SystemUserEnum


class AuthAdminSite(AdminSite):
    auth: Auth = None
    UserAuthApp: Type[DefaultUserAuthApp] = DefaultUserAuthApp

    def __init__(self, settings: Settings, fastapi: FastAPI = None, engine: SqlalchemyDatabase = None, auth: Auth = None):
        super().__init__(settings, fastapi, engine)
        self.auth = auth or self.auth or Auth(db=self.db)
        self.register_admin(self.UserAuthApp)
        CasbinRuleAdmin.enforcer = self.auth.enforcer
        self.register_admin(CasbinRuleAdmin)

    async def get_page(self, request: Request) -> App:
        app = await super().get_page(request)
        user_auth_app = self.get_admin_or_create(self.UserAuthApp)
        username = await self.auth.get_current_user_identity(request) or SystemUserEnum.GUEST
        app.header = Flex(
            className="w-full",
            justify="flex-end",
            alignItems="flex-end",
            items=[
                app.header,
                {
                    "type": "dropdown-button",
                    "label": f"{username}",
                    "trigger": "hover",
                    "icon": "fa fa-user",
                    "buttons": [
                        ActionType.Dialog(
                            label=_("User Profile"),
                            dialog=Dialog(
                                title=_("User Profile"),
                                actions=[],
                                size=SizeEnum.lg,
                                body=Service(
                                    schemaApi=AmisAPI(
                                        method="post",
                                        url=f"{user_auth_app.router_path}/form/userinfo",
                                        cache=600000,
                                        responseData={"&": "${body}"},
                                    )
                                ),
                            ),
                        ),
                        ActionType.Url(label=_("Sign out"), url=f"{user_auth_app.router_path}/logout"),
                    ],
                },
            ],
        )
        return app

    async def has_page_permission(self, request: Request, obj: PageSchemaAdmin = None, action: str = None) -> bool:
        obj = obj or self
        subject = await self.auth.get_current_user_identity(request) or SystemUserEnum.GUEST
        effect = self.auth.enforcer.enforce(subject, obj.unique_id, f"admin:{action}")
        print("casbin", subject, obj.unique_id, action, effect)
        # if subject==SystemUserEnum.GUEST and isinstance(obj, AdminGroup) and action == "page":
        #     # 对于已登录的用户, 管理分组暂时不验证权限. 因为菜单可能移动到其他分组, 会导致权限验证失败.
        #     return True
        return effect
